from nexfile import nexwriter2
import pynwb
import sys
from tqdm import trange
import numpy as np
import argparse


def nwb_to_nex5(nwb_path, elecseries_name, nex5_path):
    """
    Write the given NWB ElectricalSeries to a NEX5 file.
    :param nwb_path: path to the NWB file.
    :param elecseries_name: name of the ElectricalSeries to be written to file.
    :param nex5_path: path to the NEX5 file to be written.
    """
    with pynwb.NWBHDF5IO(nwb_path, 'r') as io:
        nwb = io.read()
        if elecseries_name not in nwb.acquisition:
            raise Exception('NWB file %s does not have an acquisition named %s.' % (nwb_path, elecseries_name))

        elecseries = nwb.acquisition[elecseries_name]
        if not isinstance(elecseries, pynwb.ecephys.ElectricalSeries):
            raise Exception('Acquisition %s must be of type ElectricalSeries.' % (elecseries_name))
        if elecseries.data.dtype is not np.dtype(np.int16):
            raise Exception('Acquisition %s must have int16 data.' % (elecseries_name))

        nChannels = elecseries.data.shape[1]
        timestampFrequency = elecseries.rate
        conversion = elecseries.conversion*1000  # NEX5 stores data in millivolts, not volts

        print(('Found ElectricalSeries "%s" with %d samples, %d channels, sampling rate %d Hz, AD to mV conversion '
               'factor %f') % (elecseries_name, elecseries.data.shape[0], nChannels, timestampFrequency, conversion))

        writer = nexwriter2.NexWriter2(timestampFrequency, useNumpy=True)
        for ch in trange(nChannels, desc='writing channels'):
            writer.AddContVarWithSingleFragment(
                name='channel_'+str(ch),
                timestampOfFirstDataPoint=0,
                SamplingRate=timestampFrequency,
                values=nwb.acquisition[elecseries_name].data[:, ch]  # data is in int16
            )

        writer.WriteNex5File(nex5_path, conversion=conversion)


def main():
    parser = argparse.ArgumentParser("A script to write an ElectricalSeries in an NWB file to a NEX5 file.")
    parser.add_argument(
        "nwb_path", help="The path to the NWB file."
    )
    parser.add_argument(
        "elecseries_name", help="The name of the ElectricalSeries to be written to file."
    )
    parser.add_argument(
        "nex5_path", help="The path to the NEX5 file to be written."
    )
    args = parser.parse_args()
    nwb_to_nex5(args.nwb_path, args.elecseries_name, args.nex5_path)


if __name__ == '__main__':
    main()
