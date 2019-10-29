import os
import numpy as np
from datetime import datetime
from buffalonwb.exceptions import InconsistentInputException, UnexpectedInputException
from uuid import UUID
from struct import unpack
from warnings import warn
from hdmf.data_utils import DataChunkIterator
from pynwb.ecephys import ElectricalSeries
from tqdm import trange
from natsort import natsorted


_CSC_HEADER_SIZE = 16384  # bytes
_CSC_SAMPLES_PER_RECORD = 512  # int16 array
_CSC_RECORD_HEADER_SIZE = 20  # 1 uint64 (1*8) + 3 uint32 (3*4)
_CSC_RECORD_SIZE = _CSC_RECORD_HEADER_SIZE + _CSC_SAMPLES_PER_RECORD * 2


def add_raw_nlx_data(nwbfile, raw_nlx_path, electrode_table_region):
    print("adding raw nlx data")

    # get paths to all CSC data files, excluding the 16 kB header files with '_' in the name
    data_files = natsorted([x.name for x in raw_nlx_path.glob('CSC*.ncs') if '_' not in x.stem])
    data_paths = [raw_nlx_path / x for x in data_files]

    # read first file to initialize a few variables
    first_filename = str(data_paths[0])
    raw_header = read_header(first_filename)
    conversion_factor = raw_header['ADBitVolts']
    rate = float(raw_header["SamplingFrequency"])

    first_ts = read_first_timestamp(first_filename)
    breakpoint()

    num_electrodes = 2
    # num_electrodes = len(electrode_table_region)
    data = raw_generator(raw_nlx_path, num_electrodes)
    ephys_data = DataChunkIterator(data=data,
                                   iter_axis=1,
                                   dtype=np.dtype('int16'))

    ephys_ts = ElectricalSeries(name='raw_ephys',
                                data=ephys_data,
                                electrodes=electrode_table_region,
                                starting_time=first_ts,
                                rate=rate,
                                conversion=conversion_factor,
                                description="This is a recording from hippocampus")
    nwbfile.add_acquisition(ephys_ts)


def raw_generator(raw_nlx_path, num_electrodes):
    """Generator that returns an array of all of the raw data for a single channel (from a single CSC .ncs file)
    """
    data_files = natsorted([x.name for x in raw_nlx_path.glob('CSC*.ncs') if '_' not in x.stem])
    data_paths = [raw_nlx_path / x for x in data_files]

    # generate raw data chunks for data chunk iterator
    for i in trange(num_electrodes, desc='writing raw data'):
        _, _, raw_data = read_csc_file(str(data_paths[i]))
        yield raw_data.astype(np.int16)


def read_header(csc_data_file_name):
    """Read the header (first 16 kB) of a CSC file
    """
    with open(csc_data_file_name, 'rb') as data_file:
        header = data_file.read(_CSC_HEADER_SIZE)
        header_data = parse_header(header)
        return header_data


def parse_header(header):  # noqa: C901
    """Parse the 16 kB header of a Neuralynx CSC (.ncs) file into a dictionary.
    Input:
      header -- 16384 bytes of header contents
    Returns dictionary of header metadata
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


def check_num_records(csc_data_file_name):
    """Check that the size of the file is consistent with an integer number of records and return the number of records.
    """
    file_size = os.path.getsize(csc_data_file_name)
    num_records = (file_size - _CSC_HEADER_SIZE) / _CSC_RECORD_SIZE
    if int(num_records) != num_records:  # check integer
        raise UnexpectedInputException('Number of records in %s must be an integer: %d' %
                                       (csc_data_file_name, num_records))
    return int(num_records)


def read_csc_file(csc_data_file_name):
    """Read and parse a CSC .ncs file.
    """
    num_records = check_num_records(csc_data_file_name)

    channel_number = None
    Fs = None
    ts = np.ndarray((num_records * _CSC_SAMPLES_PER_RECORD, ), dtype=np.uint64)
    data = np.ndarray((num_records * _CSC_SAMPLES_PER_RECORD, ))

    with open(csc_data_file_name, 'rb') as data_file:
        header = data_file.read(_CSC_HEADER_SIZE)
        header_data = parse_header(header)

        # first_ts_r: Cheetah timestamp for this record. This corresponds to the sample time for the first data point
        # in the data array, in MICROseconds. This timestamp appears not to have any real-world meaning.
        # channel_number_r: The channel number for this record. This is NOT the A/D channel number.
        # Fs_r: The sampling frequency (Hz) for the data array.
        # num_valid_samples_r: Number of values in the data array containing valid data (max 512).
        record_ind = 0
        while record_ind < num_records:
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
            record_ind = record_ind + 1

        # is there still data in the file?
        leftover_data = data_file.read()
        if leftover_data:
            raise InconsistentInputException()
        del leftover_data

        # delete invalid entries if last num_valid_samples_r != samples_per_record
        ts = np.delete(ts, np.s_[-(_CSC_SAMPLES_PER_RECORD - num_valid_samples_r):])
        data = np.delete(data, np.s_[-(_CSC_SAMPLES_PER_RECORD - num_valid_samples_r):])

        # check that final timestamp makes sense
        expected_last_ts = ts[0] + len(ts) * 1e6 / Fs
        if abs(expected_last_ts - ts[-1]) > 0:
            warn(('Last timestamp expected to be %d us based on starting time and sampling rate, but got %d us '
                  '(difference of %0.3f ms)') % (expected_last_ts, ts[-1], (expected_last_ts - ts[-1]) / 1000))

        return header_data, ts, data


def read_first_timestamp(csc_data_file_name):
    """Read just the first timestamp of a CSC .ncs file.
    """

    with open(csc_data_file_name, 'rb') as data_file:
        data_file.seek(_CSC_HEADER_SIZE)

        # first_ts_r: Cheetah timestamp for this record. This corresponds to the sample time for the first data point
        # in the data array, in MICROseconds. This timestamp appears not to have any real-world meaning.
        first_ts_r = np.fromfile(data_file, dtype='<Q', count=1)
        return first_ts_r[0]
