from nexfile import nexwriter2
import pynwb
import sys
from tqdm import trange


def nwb_to_nex5(nwb_path, nex5_path):
    with pynwb.NWBHDF5IO(nwb_path, 'r') as io:
        nwb = io.read()
        raw_data_name = 'raw_ephys'
        nChannels = nwb.acquisition[raw_data_name].data.shape[1]
        timestampFrequency = nwb.acquisition[raw_data_name].rate
        writer = nexwriter2.NexWriter2(timestampFrequency, useNumpy=True)
        for ch in trange(nChannels, desc='writing channels'):
            writer.AddContVarWithSingleFragment(
                name='channel_'+str(ch),
                timestampOfFirstDataPoint=0,
                SamplingRate=timestampFrequency,
                values=nwb.acquisition[raw_data_name].data[:, ch]  # data is in int16
            )

        # NEX5 stores data in millivolts, not volts
        conversion = nwb.acquisition[raw_data_name].conversion*1000

        writer.WriteNex5File(nex5_path, conversion=conversion)


if __name__ == '__main__':
    nwb_to_nex5(sys.argv[1], sys.argv[2])
