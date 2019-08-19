import sys
import numpy as np
from h5py import File
from buffalonwb.exceptions import InconsistentInputException, UnexpectedInputException


"""
There are 124 data files, CSC1_ex.mat to CSC124_ex.mat. Each file seems to represent the spike times and waveforms
after thresholding and the downsampled LFP values.
TODO: it might be worth verifying that all 124 data files were processed the same way, i.e. all values are the same
except for chname, lfp, spk, and spkwv
"""


def process_nlx_mat_file(nlx_file_name):
    with File(nlx_file_name, 'r') as nlx_file:
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
        if lfp_Fs != nlx_file['params']['lfpfq'][0][0]:
            raise UnexpectedInputException()

        # lfp values -- units?
        lfp = nlx_file['lfp'][()]
        if lfp.shape[0] != 1:
            raise UnexpectedInputException()

        # lfp timestamps, num columns should match num columns of lfp
        lfp_ts = nlx_file['lfpts'][()]
        if lfp_ts.shape != lfp.shape:
            raise UnexpectedInputException()

        # check lfp_ts, then keep only starting time (first_lfp_ts) and rate (lfp_Fs)
        diff_lfp_ts = np.diff(lfp_ts)
        if (abs(diff_lfp_ts[0][0] - 1/lfp_Fs) > 1e-8).any():
            raise InconsistentInputException()
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


def check_get_scalar(v):
    if v.shape != (1, 1):
        raise UnexpectedInputException()
    if v[0].shape != (1,):
        raise UnexpectedInputException()
    return v[0][0]


def main():
    nlx_file_name = sys.argv[1]  # .mat file
    process_nlx_mat_file(nlx_file_name)


if __name__ == '__main__':
    main()
