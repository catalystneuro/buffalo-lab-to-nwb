import sys
import os
import numpy as np
from datetime import datetime
from exceptions import InconsistentInputException, UnexpectedInputException
from uuid import UUID
from struct import unpack


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
    with open(csc_data_file_name, 'rb') as data_file:
        header = data_file.read(16384)
        header_data = parse_header(header)

        # data_file[16384:16388] unknown
        data_file.seek(16384, os.SEEK_SET)
        unknown = data_file.read(4)

        # first_timestamp: Cheetah timestamp for this record. This corresponds to the
        # sample time for the first data point in the snSamples array.
        # This value is in microseconds.
        # channel_number: The channel number for this record. This is NOT the A/D channel number.
        # Fs: The sampling frequency (Hz) for the data stored in data.
        # num_valid_samples: Number of values in data containing valid data (fixed to 512).
        first_timestamp, channel_number, Fs, num_valid_samples = unpack('<LIII', data_file.read(16))
        if num_valid_samples != 512:
            raise UnexpectedInputException()

        data = np.fromfile(data_file, dtype='<u2')  # unsigned int, little endian


def main():
    # see https://neuralynx.com/software/NeuralynxDataFileFormats.pdf
    csc_data_file_name = sys.argv[1]  # .ncs file
    read_csc_file(csc_data_file_name)


if __name__ == '__main__':
    main()
