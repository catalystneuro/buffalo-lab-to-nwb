# add processed nlx data
import h5py
import numpy as np
import os
import pynwb
from pynwb.ecephys import ElectricalSeries
from hdmf.data_utils import DataChunkIterator
from buffalonwb.exceptions import UnexpectedInputException, InconsistentInputException
from tqdm import trange


def add_lfp(nwbfile, lfp_path, num_electrodes, electrodes, iterator_flag):
    if iterator_flag:
        print("adding LFP via data chunk iterator")
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
        name='LFP',
        data=lfp_data,
        electrodes=electrodes,
        starting_time=float(lfp_timestamps_sq[0]),
        rate=lfp_rate,
    )

    proc_module = nwbfile.create_processing_module(
        name='ecephys',
        description='module for processed ecephys data'
    )
    # Store LFP data in ecephys
    proc_module.add(pynwb.ecephys.LFP(electrical_series=lfp_es, name='LFP'))


# FUNCTIONS FOR PROCESSED DATA
# no input checking for now
# add back input checking soon #FIXTHIS

# process nlx mat file into dictionary
# needs: data, timestamps, resolution, time, rate
def process_nlx_mat_file(nlx_file_name):
    if not os.path.exists(nlx_file_name):
        msg = 'skipped ' + str(nlx_file_name + ', returning empty dict')
        print(msg)
        return dict()

    with h5py.File(nlx_file_name, 'r') as nlx_file:
        expected_keys = {'chname', 'firstts', 'lfpfq', 'params', 'filename', 'lfp', 'extractMethod', 'spkts', '#refs#',
                         'foldername', 'lfpts', 'spkwv', 'Fs'}
        if set(nlx_file.keys()) != expected_keys:
            raise UnexpectedInputException()

        expected_param_keys = {'lfpfq', 'n_std', 'rawspk', 'resamp', 'saveupsamp', 'spkbuff', 'spkfq'}
        if set(nlx_file['params'].keys()) != expected_param_keys:
            raise UnexpectedInputException()

        # convert from ascii ints to string
        chname = ''.join(map(chr, nlx_file['chname']))
        extract_method = ''.join(map(chr, nlx_file['extractMethod']))
        ncs_filename = ''.join(map(chr, nlx_file['filename']))  # original file name, probably not necessary

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

        # check lfp_ts, then keep only starting time (first_lfp_ts) and rate (lfp_Fs)
        """
        diff_lfp_ts = np.diff(lfp_ts)
        if (abs(diff_lfp_ts[0][0] - 1/lfp_Fs) > 1e-8).any():
            raise InconsistentInputException()
        """
        first_lfp_ts = lfp_ts[0][0]

        # get spike times
        spk_ts = nlx_file['spkts'][()]
        if spk_ts.shape[0] != 1:
            raise UnexpectedInputException()

        # get spike waveforms
        spk_wfs = nlx_file['spkwv'][()]
        if spk_wfs.shape[1] != spk_ts.shape[1]:
            raise UnexpectedInputException()

        # get preprocessing parameters
        n_std = check_get_scalar(nlx_file['params']['n_std'])  # standard deviations used for thresholding
        rawspk = check_get_scalar(nlx_file['params']['rawspk'])  # ??? 0 in sample file
        resamp = check_get_scalar(nlx_file['params']['resamp'])  # ??? 1 in sample file
        saveupsamp = check_get_scalar(nlx_file['params']['saveupsamp'])  # ??? 0 in sample file
        spkfq = check_get_scalar(nlx_file['params']['spkfq'])  # ??? 400 in sample file

        # i'm guessing spkbuff specifies num samples before threshold crossing and num samples after threshold
        spk_buff = nlx_file['params']['spkbuff'][()]
        if spk_buff.shape != (2, 1):
            raise UnexpectedInputException()
        if sum(spk_buff)[0] + 1 != spk_wfs.shape[0]:
            raise InconsistentInputException()
        spk_buff = spk_buff.transpose()[0].tolist()

        # variables of interest
        dict_vars = {'Fs', 'first_ts', 'lfp_Fs', 'lfp', 'lfp_ts', 'first_lfp_ts', 'spk_ts', 'spk_wfs', 'n_std',
                     'rawspk', 'resamp', 'saveupsamp', 'spkfq', 'spk_buff'}

        # make a dictionary
        file_dict = dict()
        for i in dict_vars:
            file_dict[i] = locals()[i]

        return file_dict


def check_get_scalar(v):
    if v.shape != (1, 1):
        raise UnexpectedInputException()
    if v[0].shape != (1,):
        raise UnexpectedInputException()
    return v[0][0]


def get_lfp_data(num_electrodes, lfp_path):
    all_files = os.listdir(lfp_path)
    processed = process_nlx_mat_file(lfp_path.joinpath(all_files[0]))
    num_ts = max(processed["lfp_ts"].shape)
    lfp = np.full((num_electrodes, num_ts), np.nan)
    ts = processed["lfp_ts"]
    fs = processed["lfp_Fs"]
    # check if ts are all the same
    for i in trange(num_electrodes, desc='reading LFP'):
        file_name = lfp_path.joinpath(all_files[i])
        processed_file = process_nlx_mat_file(file_name)
        if processed_file:
            lfp[i, :] = processed_file["lfp"]
    return lfp, ts, fs


def lfp_generator(lfp_path, num_electrodes):
    all_files = os.listdir(lfp_path)
    # generate lfp data chunks
    for i in trange(num_electrodes, desc='writing LFP'):
        file_name = lfp_path.joinpath(all_files[i])
        processed_data = process_nlx_mat_file(file_name)
        lfp_data = processed_data["lfp"]
        del processed_data
        yield np.squeeze(lfp_data).T
    return
