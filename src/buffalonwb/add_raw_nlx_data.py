import numpy as np
from datetime import datetime
from uuid import UUID
from struct import unpack
from warnings import warn
from tqdm import trange
from natsort import natsorted
from hdmf.data_utils import DataChunkIterator
from pynwb.ecephys import ElectricalSeries

from buffalonwb.exceptions import InconsistentInputException, UnexpectedInputException


_CSC_HEADER_SIZE = 16384  # bytes
_CSC_SAMPLES_PER_RECORD = 512  # int16 array
_CSC_RECORD_HEADER_SIZE = 20  # bytes: 1 uint64 (1*8) + 3 uint32 (3*4)
_CSC_RECORD_SIZE = _CSC_RECORD_HEADER_SIZE + _CSC_SAMPLES_PER_RECORD * 2


def add_raw_nlx_data(nwbfile, raw_nlx_path, electrode_table_region):
    """Add raw acquisition data from Neuralynx CSC .ncs files to an NWB file using a data chunk iterator
    :param nwbfile: The NWBFile object
    :param raw_nlx_path: Path object for directory of raw NLX CSC files
    :param electrode_table_region: The set of electrodes corresponding to these acquisition time series data. There
    should be one .ncs data file for every electrode in the electrode_table_region.
    """
    print('Adding raw NLX data using data chunk iterator')
    num_electrodes = len(electrode_table_region)

    # get paths to all CSC data files, excluding the 16 kB header files with '_' in the name
    data_files = natsorted([x.name for x in raw_nlx_path.glob('CSC*.ncs') if '_' not in x.stem])
    data_paths = [raw_nlx_path / x for x in data_files]
    assert(len(data_paths) == num_electrodes)

    # read first file fully to initialize a few variables
    raw_header, raw_ts, _ = read_csc_file(data_paths[0])
    starting_time = float(raw_ts[0])
    rate = float(raw_header['SamplingFrequency'])
    conversion_factor = raw_header['ADBitVolts']
    # TODO put header data into NWBFile under Neuraalynx device

    num_electrodes = 2
    data = raw_generator(raw_nlx_path, num_electrodes)
    ephys_data = DataChunkIterator(data=data,
                                   iter_axis=1,
                                   maxshape=(len(raw_ts), num_electrodes),
                                   dtype=np.dtype('int16'))

    # NOTE: starting time and rate are provided instead of timestamps. rate may be 32000.012966 Hz rather than 32000 Hz
    # but use the reported 32000 Hz anyway.
    ephys_ts = ElectricalSeries(name='ElectricalSeries',
                                data=ephys_data,
                                electrodes=electrode_table_region,
                                starting_time=starting_time,
                                rate=rate,
                                conversion=conversion_factor,
                                description='This is a recording from the hippocampus')
    nwbfile.add_acquisition(ephys_ts)


def raw_generator(raw_nlx_path):
    """Generator that returns an array of all of the raw data for a single channel (from a single CSC .ncs file)
    :param raw_nlx_path: Path object for directory of raw NLX CSC files
    """
    data_files = natsorted([x.name for x in raw_nlx_path.glob('CSC*.ncs') if '_' not in x.stem])
    data_paths = [raw_nlx_path / x for x in data_files]

    # generate raw data chunks for data chunk iterator
    for i in trange(len(data_paths), desc='Writing raw data'):
        _, raw_ts, raw_data = read_csc_file(data_paths[i])
        if i == 0:
            raw_ts_ch0 = raw_ts
        else:
            if not np.all(raw_ts_ch0 == raw_ts):
                raise InconsistentInputException('Timestamps are not aligned between %s and %s'
                                                 % (data_paths[0], data_paths[i]))
        yield raw_data.astype(np.int16)


def parse_header(header):  # noqa: C901
    """Parse the 16 kB header of a Neuralynx CSC (.ncs) file into a dictionary.
    :param header: 16384 bytes of header contents
    :return: dictionary of header metadata
    """
    header_data = dict()
    for line in header.splitlines():
        if not line:
            continue
        if line[0] == '\x00':  # end of file
            break

        line = ''.join(map(chr, line))
        if line[0] == '#':  # comment
            continue
        if line[0] == '-':  # metadata
            line_parts = line[1:].strip().replace('"', '').split(' ')
            key = line_parts[0]
            if len(line_parts) == 1:
                header_data[key] = None
            elif key.startswith('Time'):
                header_data[key] = datetime.strptime(' '.join(line_parts[1:]), '%Y/%m/%d %H:%M:%S')
            elif key.endswith('UUID'):
                header_data[key] = UUID(line_parts[1])
            elif key == 'ApplicationName':
                header_data[key] = line_parts[1]
                header_data['ApplicationVersion'] = line_parts[2]
            elif key == 'ReferenceChannel':
                if line_parts[1] != 'Source' or line_parts[3] != 'Reference':
                    raise UnexpectedInputException()
                header_data['ReferenceChannelSource'] = line_parts[2]
                header_data['ReferenceChannelReference'] = line_parts[4]
            elif key == 'AcquisitionSystem':
                if len(line_parts) != 3:
                    raise UnexpectedInputException()
                header_data[key] = line_parts[1] + ' ' + line_parts[2]
            else:
                if len(line_parts) > 2:
                    raise UnexpectedInputException()
                if key in {'InputInverted', 'DSPLowCutFilterEnabled', 'DSPHighCutFilterEnabled'}:
                    header_data[key] = bool(line_parts[1])
                elif key in {'RecordSize', 'SamplingFrequency', 'ADMaxValue', 'NumADChannels', 'ADChannel',
                             'InputRange', 'DspLowCutNumTaps', 'DspHighCutFrequency', 'DspHighCutNumTaps',
                             'DspFilterDelay_µs'}:
                    header_data[key] = int(line_parts[1])
                elif key in {'ADBitVolts', 'DspLowCutFrequency'}:
                    header_data[key] = float(line_parts[1])
                else:
                    header_data[key] = line_parts[1]

    expected_keys = {'FileType', 'FileVersion', 'FileUUID', 'SessionUUID', 'ProbeName', 'OriginalFileName',
                     'TimeCreated', 'TimeClosed', 'RecordSize', 'ApplicationName', 'ApplicationVersion',
                     'AcquisitionSystem', 'ReferenceChannelSource', 'ReferenceChannelReference', 'SamplingFrequency',
                     'ADMaxValue', 'ADBitVolts', 'AcqEntName',
                     'NumADChannels', 'ADChannel', 'InputRange', 'InputInverted', 'DSPLowCutFilterEnabled',
                     'DspLowCutFrequency', 'DspLowCutNumTaps', 'DspLowCutFilterType', 'DSPHighCutFilterEnabled',
                     'DspHighCutFrequency', 'DspHighCutNumTaps', 'DspHighCutFilterType', 'DspDelayCompensation',
                     'DspFilterDelay_µs'}

    if set(header_data.keys()) != expected_keys:
        raise UnexpectedInputException()

    return header_data


def check_num_records(csc_file_path):
    """Check that the size of the file is consistent with an integer number of records and return the number of records.
    :param csc_file_path: Path object for a single CSC .ncs file
    :return: the number of records in the file
    """
    file_size = csc_file_path.stat().st_size
    num_records = (file_size - _CSC_HEADER_SIZE) / _CSC_RECORD_SIZE
    if int(num_records) != num_records:  # check integer
        raise UnexpectedInputException('Number of records in %s must be an integer: %d' %
                                       (str(csc_file_path), num_records))
    return int(num_records)


def read_csc_file(csc_file_path):
    """Read and parse a CSC .ncs file.
    :param csc_file_path: Path object for a single CSC .ncs file
    :return: tuple of header data, timestamps, and data values from the file
    """
    num_records = check_num_records(csc_file_path)

    channel_number = None
    Fs = None
    ts = np.ndarray((num_records * _CSC_SAMPLES_PER_RECORD, ), dtype=np.uint64)
    data = np.ndarray((num_records * _CSC_SAMPLES_PER_RECORD, ))

    with open(csc_file_path, 'rb') as data_file:
        header = data_file.read(_CSC_HEADER_SIZE)
        header_data = parse_header(header)

        # first_ts_r: Cheetah timestamp for this record. This corresponds to the sample time for the first data point
        # in the data array, in MICROseconds. This timestamp appears not to have any real-world meaning.
        # channel_number_r: The channel number for this record. This is NOT the A/D channel number.
        # Fs_r: The sampling frequency (Hz) for the data array.
        # num_valid_samples_r: Number of values in the data array containing valid data (max 512).
        # NOTE: for nested progress bars on Windows, the colorama package is required
        for record_ind in trange(num_records, desc='Reading raw data: %s' % csc_file_path.stem, leave=False):
            read_record_header = data_file.read(_CSC_RECORD_HEADER_SIZE)
            first_ts_r, channel_number_r, Fs_r, num_valid_samples_r = unpack('<QIII', read_record_header)

            if record_ind == 0:
                channel_number = channel_number_r
                Fs = Fs_r
                if num_valid_samples_r != _CSC_SAMPLES_PER_RECORD:
                    raise UnexpectedInputException()
            else:  # verify matching record
                # first timestamp of the record might not be what we expect it to be -- see warning later
                if not (channel_number == channel_number_r and Fs == Fs_r):
                    raise InconsistentInputException()
                # OK if last record has fewer than 512 valid samples -- handle in delete below
                if record_ind < num_records - 1 and num_valid_samples_r != _CSC_SAMPLES_PER_RECORD:
                    raise InconsistentInputException()

            data_ind_start = record_ind * _CSC_SAMPLES_PER_RECORD
            data_ind_end = data_ind_start + _CSC_SAMPLES_PER_RECORD
            ts[data_ind_start:data_ind_end] = np.arange(first_ts_r,
                                                        first_ts_r + _CSC_SAMPLES_PER_RECORD * 1e6 / Fs,
                                                        1e6 / Fs)
            data[data_ind_start:data_ind_end] = np.fromfile(data_file, dtype='<h', count=_CSC_SAMPLES_PER_RECORD)

        # is there still data in the file?
        leftover_data = data_file.read()
        if leftover_data:
            raise InconsistentInputException()
        del leftover_data

        # delete invalid entries if last num_valid_samples_r != samples_per_record
        ts = np.delete(ts, np.s_[-(_CSC_SAMPLES_PER_RECORD - num_valid_samples_r):])
        data = np.delete(data, np.s_[-(_CSC_SAMPLES_PER_RECORD - num_valid_samples_r):])

        # check that final timestamp makes sense
        # NOTE: a discrepancy of 1 us occurs approximately once every 155-157 records, resulting in a sampling rate
        # just larger than 32 kHz
        expected_last_ts = ts[0] + len(ts) * 1e6 / Fs
        if abs(expected_last_ts - ts[-1]) > 0:
            warn(('Last timestamp expected to be %d us based on starting time and sampling rate, but got %d us '
                  '(difference of %0.3f ms). Actual sampling rate may be %f Hz.')
                 % (expected_last_ts, ts[-1], (expected_last_ts - ts[-1]) / 1000, 1e6 * len(ts) / (ts[-1] - ts[0])))

        return header_data, ts, data
