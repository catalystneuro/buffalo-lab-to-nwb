import os
import numpy as np
from datetime import datetime
from exceptions import InconsistentInputException, UnexpectedInputException
from uuid import UUID
from struct import unpack
from warnings import warn


# add raw nlx data
def add_raw_nlx_data(nwbfile,raw_nlx_file,electrode_table_region,num_electrodes):
    print("adding raw nlx data")
    raw_header, raw_ts, data =read_csc_file(''.join([raw_nlx_file.split("%")[0], str(1), raw_nlx_file.split("%")[1]]))

    rate = raw_header["SamplingFrequency"]
    ephys_data = DataChunkIterator(data=raw_generator,iter_axis=1,maxshape=(len(raw_ts),num_electrodes))
    ephys_timestamps=raw_ts

    ephys_ts = ElectricalSeries('raw_ephys',
                                ephys_data,
                                electrode_table_region,
                                timestamps=ephys_timestamps,
                                resolution=1/rate,
                                comments="This is an electrical series",
                                description="This is a recording from hippocamus")
    nwbfile.add_acquisition(ephys_ts)

def raw_generator(raw_nlx_file):
    #generate raw data chunks for iterator
    x=0
    num_chunks=3
    while(x<num_chunks):
        file_name=''.join([raw_nlx_file.split("%")[0], str(x), raw_nlx_file.split("%")[1]])
        raw_header, raw_ts, raw_data =read_csc_file(file_name)
        x+=1
        yield raw_data
    return

# RAW DATA FUNCTIONS
def parse_header(header):
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
                    breakpoint()
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


def read_csc_file(csc_data_file_name):
    header_size = 16384
    samples_per_record = 512
    record_header_size = 20
    record_size = record_header_size + samples_per_record * 2  # matches '<QIII' + 512 * 'h'

    file_size = os.path.getsize(csc_data_file_name)
    num_records = (file_size - header_size) / record_size
    if int(num_records) != num_records:  # check integer
        raise UnexpectedInputException()
    num_records = int(num_records)

    channel_number = None
    Fs = None
    ts = np.ndarray((num_records * samples_per_record, ), dtype=np.uint64)
    data = np.ndarray((num_records * samples_per_record, ))

    with open(csc_data_file_name, 'rb') as data_file:
        header = data_file.read(header_size)
        header_data = parse_header(header)

        # first_ts_r: Cheetah timestamp for this record. This corresponds to the sample time for the first data point
        # in the data array, in MICROseconds.
        # channel_number_r: The channel number for this record. This is NOT the A/D channel number.
        # Fs_r: The sampling frequency (Hz) for the data array.
        # num_valid_samples_r: Number of values in the data array containing valid data (max 512).
        record_ind = 0
        while record_ind < num_records:
            read_record_header = data_file.read(record_header_size)
            first_ts_r, channel_number_r, Fs_r, num_valid_samples_r = unpack('<QIII', read_record_header)

            if record_ind == 0:
                channel_number = channel_number_r
                Fs = Fs_r
                if num_valid_samples_r != samples_per_record:
                    raise UnexpectedInputException()
            else:  # verify matching record
                # first timestamp of the record might not be what we expect it to be -- see warning later
                if not (channel_number == channel_number_r and Fs == Fs_r):
                    raise InconsistentInputException()
                # OK if last record has fewer than 512 valid samples -- handle in delete below
                if record_ind < num_records - 1 and num_valid_samples_r != samples_per_record:
                    raise InconsistentInputException()

            data_ind_start = record_ind * samples_per_record
            data_ind_end = data_ind_start + samples_per_record
            ts[data_ind_start:data_ind_end] = np.arange(first_ts_r,
                                                        first_ts_r + samples_per_record * 1e6 / Fs,
                                                        1e6 / Fs)
            data[data_ind_start:data_ind_end] = np.fromfile(data_file, dtype='<h', count=samples_per_record)
            record_ind = record_ind + 1

        # is there still data in the file?
        leftover_data = data_file.read()
        if leftover_data:
            raise InconsistentInputException()

        # delete invalid entries if last num_valid_samples_r != samples_per_record
        ts = np.delete(ts, np.s_[-(samples_per_record - num_valid_samples_r):])
        data = np.delete(data, np.s_[-(samples_per_record - num_valid_samples_r):])

        # check final timestamp makes sense
        expected_last_ts = ts[0] + len(ts) * 1e6 / Fs
        if abs(expected_last_ts - ts[-1]) > 0:
            warn(('Last timestamp expected to be %d us based on starting time and sampling rate, but got %d us '
                  '(difference of %0.3f ms)') % (expected_last_ts, ts[-1], (expected_last_ts - ts[-1]) / 1000))

        return header_data, ts, data

