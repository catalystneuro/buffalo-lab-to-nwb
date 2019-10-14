from nexfile import nexfile
import pynwb
import numpy as np

def nwb_to_nex5(nwb_path, nex5_path):
    io = pynwb.NWBHDF5IO(nwb_path, 'r')
    nwb = io.read()
    nChannels = nwb.acquisition['ElectricalSeries'].data.shape[1]
    conversion = nwb.acquisition['ElectricalSeries'].conversion*1000
    timestampFrequency = nwb.acquisition['ElectricalSeries'].rate
    writer = nexfile.NexWriter(timestampFrequency, useNumpy=True)
    for ch in np.arange(nChannels):
        writer.AddContVarWithSingleFragment(
            name='channel_'+str(ch),
            timestampOfFirstDataPoint=0,
            SamplingRate=timestampFrequency,
            values=nwb.acquisition['ElectricalSeries'].data[:, ch]*conversion
        )
    writer.WriteNex5File(nex5_path, saveContValuesAsFloats=1)
    io.close()
