from nexfile import nexwriter2
import pynwb
from tqdm import trange
import numpy as np
import argparse
import datetime


def nwb_to_nex5(nwb_path, nex5_path, elecseries_name='ElectricalSeries'):
    """
    Write the given NWB ElectricalSeries to a NEX5 file.
    :param nwb_path: path to the NWB file.
    :param elecseries_name: name of the ElectricalSeries in the NWB file to be written to the NEX5 file.
    :param nex5_path: path to the NEX5 file to be written.
    """

    with pynwb.NWBHDF5IO(nwb_path, 'r') as io:
        nwb = io.read()
        if elecseries_name not in nwb.acquisition:
            raise Exception('NWB file %s does not have an acquisition named "%s".' % (nwb_path, elecseries_name))

        elecseries = nwb.acquisition[elecseries_name]
        if not isinstance(elecseries, pynwb.ecephys.ElectricalSeries):
            raise Exception('Acquisition "%s" must be of type ElectricalSeries.' % (elecseries_name))
        if elecseries.data.dtype is not np.dtype(np.int16):
            raise Exception('Acquisition "%s" must have int16 data.' % (elecseries_name))

        num_channels = elecseries.data.shape[1]
        # use electricalseries start time, which is relative to timestamps_reference_time
        start_time = elecseries.starting_time
        timestamp_freq = elecseries.rate
        conversion = elecseries.conversion*1000  # NEX5 stores data in millivolts, not volts

        print('Found ElectricalSeries "%s" data:' % elecseries_name)
        print('Num channels: \t\t\t%d' % num_channels)
        print('Num samples: \t\t\t%d' % elecseries.data.shape[0])
        print('Sampling rate: \t\t\t%f Hz' % timestamp_freq)
        print('Total time: \t\t\t%f seconds' % (elecseries.data.shape[0] / timestamp_freq))
        print('AD to mV conversion factor: \t%f' % conversion)
        print('ElectricalSeries starting time: %f seconds' % start_time)
        print('Timestamps reference time: \t%s' % nwb.timestamps_reference_time)
        print('')

        # use modified nexwriter in order to handle AD (int16) data and given conversion factor
        writer = nexwriter2.NexWriter2(timestamp_freq, useNumpy=True)
        for ch in trange(num_channels, desc='Writing channels to NEX5 file'):
            writer.AddContVarWithSingleFragment(
                name='channel_'+str(ch),
                timestampOfFirstDataPoint=start_time,
                SamplingRate=timestamp_freq,
                values=elecseries.data[:, ch]
            )

        writer.WriteNex5File(nex5_path, conversion=conversion)


def main():
    parser = argparse.ArgumentParser("A script to write an ElectricalSeries in an NWB file to a NEX5 file.")
    parser.add_argument(
        "nwb_path", help="The path to the NWB file."
    )
    parser.add_argument(
        "elecseries_name",
        help="The name of the ElectricalSeries in the NWB file to be written to the NEX5 file.",
    )
    parser.add_argument(
        "nex5_path", help="The path to the NEX5 file to be written."
    )
    args = parser.parse_args()
    nwb_to_nex5(args.nwb_path, args.nex5_path, args.elecseries_name)


if __name__ == '__main__':
    main()
