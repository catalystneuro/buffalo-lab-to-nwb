# add processed nlx data
import h5py
from pynwb.ecephys import ElectricalSeries
import numpy as np
import os
import pynwb
from hdmf.data_utils import DataChunkIterator
from buffalonwb.exceptions import UnexpectedInputException
from tqdm import trange


def add_lfp(nwbfile, lfp_path, num_electrodes, electrodes, iterator_flag):
    if iterator_flag:
        print("LFP adding via data chunk iterator")
        lfp, lfp_timestamps, lfp_rate = get_lfp_data(num_electrodes=1, lfp_path=lfp_path)
        lfp_gen = lfp_generator(lfp_path=lfp_path, num_electrodes=num_electrodes)
        lfp_data = DataChunkIterator(data=lfp_gen, iter_axis=1)
    else:
        lfp_data, lfp_timestamps, lfp_rate = get_lfp_data(num_electrodes=num_electrodes, lfp_path=lfp_path)

    lfp_timestamps_sq = np.squeeze(lfp_timestamps)
    # if 1/(lfp_timestamps_sq[1]-lfp_timestamps_sq[0]) !=lfp_rate:
    #     print("not equal to rate!!")
    #     print(str(lfp_timestamps_sq[1]-lfp_timestamps_sq[0]))
    #     print(str(lfp_rate))

    # time x 120
    # add the lfp metadata - some in the lab metadata and some in the electrical series
    lfp_es = ElectricalSeries(
        name='ElectricalSeries_lfp',
        data=lfp_data,
        electrodes=electrodes,
        starting_time=float(lfp_timestamps_sq[0]),
        rate=lfp_rate,
        comments="LFP",
        description="LFP"
    )

    proc_module = nwbfile.create_processing_module(
        name='ecephys',
        description='module for processed data'
    )
    # Store LFP data in ecephys
    proc_module.add(pynwb.ecephys.LFP(electrical_series=lfp_es, name='LFP'))


# FUNCTIONS FOR PROCESSED DATA
# no input checking for now
# add back input checking soon #FIXTHIS

# process nlx mat file into dictionary
# needs: data, timestamps, resolution, time, rate
def MH_process_nlx_mat_file(nlx_file_name):
    # for some reason files 7-9 don't exist
    # as a stop gap we'll skip them
    # FIXTHIS
    if os.path.exists(nlx_file_name):
        nlx_file = h5py.File(nlx_file_name, 'r')
    else:
        msg = 'skipped ' + str(nlx_file_name + ', returning empty dict')
        print(msg)
        return dict()

    # raw sampling frequency
    Fs = check_get_scalar(nlx_file['Fs'][()])

    # first timestamp in raw data
    first_ts = check_get_scalar(nlx_file['firstts'][()])

    # lfp sampling frequency, should be same as value in params.lfpfq
    lfp_Fs = check_get_scalar(nlx_file['lfpfq'][()])

    # lfp values -- units?
    lfp = nlx_file['lfp'][()]

    # lfp timestamps, num columns should match num columns of lfp
    lfp_ts = nlx_file['lfpts'][()]
    lfp_ts = nlx_file['lfpts'][()]

    # check lfp_ts, then keep only starting time (first_lfp_ts) and rate (lfp_Fs)
    diff_lfp_ts = np.diff(lfp_ts)
    first_lfp_ts = lfp_ts[0][0]

    # get spike times
    spk_ts = nlx_file['spkts'][()]

    # get spike waveforms
    spk_wfs = nlx_file['spkwv'][()]

    # get preprocessing parameters
    n_std = check_get_scalar(nlx_file['params']['n_std'])  # standard deviations used for thresholding
    rawspk = check_get_scalar(nlx_file['params']['rawspk'])  # ??? 0 in sample file
    resamp = check_get_scalar(nlx_file['params']['resamp'])  # ??? 1 in sample file
    saveupsamp = check_get_scalar(nlx_file['params']['saveupsamp'])  # ??? 0 in sample file
    spkfq = check_get_scalar(nlx_file['params']['spkfq'])  # ??? 400 in sample file
    # MH- ??? what is up with this #FIXTHIS

    # i'm guessing spkbuff specifies num samples before threshold crossing and num samples after threshold
    spk_buff = nlx_file['params']['spkbuff'][()]
    spk_buff = spk_buff.transpose()[0].tolist()

    # variables of interest
    dict_vars = {'Fs', 'first_ts', 'lfp_Fs', 'lfp', 'lfp_ts', 'first_lfp_ts', 'spk_ts', 'spk_wfs', 'n_std', 'rawspk',
                 'resamp', 'saveupsamp', 'spkfq', 'spk_buff'}

    # make a dictionary
    file_dict = dict()
    for i in dict_vars:
        file_dict[i] = locals()[i]

    # DELETE NLX FILE TO CLEAN MEMORY
    del nlx_file

    return file_dict


def check_get_scalar(v):
    if v.shape != (1, 1):
        raise UnexpectedInputException()
    if v[0].shape != (1,):
        raise UnexpectedInputException()
    return v[0][0]


def get_lfp_data(num_electrodes, lfp_path):
    all_files = os.listdir(lfp_path)
    processed = MH_process_nlx_mat_file(lfp_path.joinpath(all_files[0]))
    num_ts = max(processed["lfp_ts"].shape)
    lfp = np.full((num_electrodes, num_ts), np.nan)
    ts = processed["lfp_ts"]
    fs = processed["lfp_Fs"]
    # check if ts are all the same
    for i in trange(0, num_electrodes, desc='reading LFP'):
        file_name = lfp_path.joinpath(all_files[i])
        processed_file = MH_process_nlx_mat_file(file_name)
        if processed_file:
            lfp[i, :] = processed_file["lfp"]
    return lfp, ts, fs


def lfp_generator(lfp_path, num_electrodes):
    all_files = os.listdir(lfp_path)
    # generate lfp data chunks
    for i in trange(0, num_electrodes, desc='writing LFP'):
        file_name = lfp_path.joinpath(all_files[i])
        processed_data = MH_process_nlx_mat_file(file_name)
        lfp_data = processed_data["lfp"]
        del processed_data
        yield np.squeeze(lfp_data).T
    return
