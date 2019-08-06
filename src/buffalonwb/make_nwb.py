# NOTES TO SELF
# - Later get all vars out of text file
# - Where do the device and electrode locations come from?
# - What is their setup?
# - Add the behavior
# - Reaching out to Yoni
#    A) Processing code
#    B) Somewhere to read Methods? Paper?
#    C)
#
# TO DO:
# - Electrical series
# - Behavior as... trials?
# - Eye behavior as time series?
#


# IMPORTING
# Currently copy/pasted
from datetime import datetime
from dateutil.tz import tzlocal
import pytz
from pynwb import NWBFile
from pynwb import NWBHDF5IO
import numpy as np
import math
from pynwb.ecephys import ElectricalSeries
import h5py
import os
# MAKE SETUP FILE
import sys
sys.path.insert(0,'C:\\Users\\Maija\\Documents\\NWB\\buffalo-lab-data-to-nwb\\src\\nexfile')
import nexfile

# files for jupyter
lfp_mat_file = 'ADDME'
sorted_spikes_nex5_file = '2017-04-27_11-41-21_sorted.nex5'
sorted_spikes_nex5_file = 'C:\\Users\\Maija\\Documents\\NWB\\buffalo-data\\SortedSpikes\\2017-04-27_11-41-21_sorted.nex5'
behavior_eye_file = 'MatFile_2017-04-27_11-41-21.mat'


# provide relevant file information
# this should grab from a text file #FIXTHIS


# file information  (what/when)
identifier = 'ADDME'
session_description = 'ADDME'
session_id = 'ADDME'
session_start_time = datetime.now()
timestamps_reference_time = datetime.now()
timezone = pytz.timezone('US/Pacific')

# file information (who/where)
experimenter = 'Yoni Browning'
lab = 'Buffalo Lab'
institution = 'University of Washington'

# notes about data collection and analyis (why/how)
notes = 'ADDME'
stimulus_notes = 'ADDME'
data_collection = 'ADDME'
experiment_description = 'ADDME'
protocol = 'ADDME'
keywords = ['ADDME']


# Make NWB file
# now that we have all the relevant information, we'll make the NWB file
# https://pynwb.readthedocs.io/en/stable/pynwb.file.html
session_start_time = timezone.localize(session_start_time)
timestamps_reference_time = timezone.localize(timestamps_reference_time)
nwbfile = NWBFile(session_description=session_description,
                  identifier=identifier,
                  session_id=session_id,
                  session_start_time=session_start_time,
                  timestamps_reference_time=timestamps_reference_time,
                  notes=notes,
                  stimulus_notes=stimulus_notes,
                  data_collection=data_collection,
                  experiment_description=experiment_description,
                  protocol=protocol,
                  keywords=keywords,
                  experimenter=experimenter,
                  lab=lab,
                  institution=institution)



# to add the electrical series we need the nlx file data
# ryan style
# this file needs: data, timestamps, resolution, time, rate
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


# no input checking for now
# add back input checking soon #FIXTHIS

# process nlx mat file into dictonary
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
    for i in (dict_vars):
        file_dict[i] = locals()[i]

    return file_dict

# Add device
# NWB needs to know what recording device we used before we can make any electrode groups
device_name = 'Neuralynx ADDME'
device = nwbfile.create_device(name=device_name)

# Add electrodes
# electrode groups each need a name, location and device
eg_name = 'Gray Matter Array ADDME'
eg_description = 'ADDME'
eg_location = 'Hippocampus ADDME'
eg_device = device
electrode_group = nwbfile.create_electrode_group(name=eg_name,
                                                 description=eg_description,
                                                 location=eg_location,
                                                 device=device)

# electrodes each need an ID from 1-num_electrodes
# https://pynwb.readthedocs.io/en/stable/pynwb.file.html#pynwb.file.NWBFile.add_electrode
# we'll need to get the electrode information from Yoni
num_electrodes = 124
for id in range(1, num_electrodes+1):
    nwbfile.add_electrode(x=math.nan,  # ADDME
                          y=math.nan,
                          z=math.nan,
                          imp=math.nan,
                          location=electrode_group.location,
                          filtering='none',
                          group=electrode_group,
                          id=id)

#add electrical series
# this is from the tutorial - replace with the actual data from nlx files
electrode_table_region = nwbfile.create_electrode_table_region([0, 2], 'the first and third electrodes')
rate = 10.0
np.random.seed(1234)
data_len = 1000
ephys_data = np.random.rand(data_len * 2).reshape((data_len, 2))
ephys_timestamps = np.arange(data_len) / rate

ephys_ts = ElectricalSeries('test_ephys_data',
                            ephys_data,
                            electrode_table_region,
                            timestamps=ephys_timestamps,
                            # Alternatively, could specify starting_time and rate as follows
                            # starting_time=ephys_timestamps[0],
                            # rate=rate,
                            resolution=0.001,
                            comments="This data was randomly generated with numpy, using 1234 as the seed",
                            description="Random numbers generated with numpy.random.rand")
nwbfile.add_acquisition(ephys_ts)


# adding
lfp_data = ephys_data
lfp_timestamps = ephys_timestamps
lfp_resolution= 0.001

# LFP DATA
lfp_ts = ElectricalSeries('test_lfp',
                         lfp_data,
                         electrode_table_region,
                         timestamps=lfp_timestamps,
                         resolution=lfp_resolution,
                         comments="LFP- is it unfiltered?",
                         description='LFP')

# put LFP data in ecephys
# what is the most efficient/pythonic way to do this?

#from pynwb.ecephys import LFP
#lfp = LFP(lfp_ts)
#nwbfile.add_acquisition(lfp)

pynwb.ecephys.LFP(electrical_series=lfp_ts, name='LFP')

# From Ryan Ly
def add_units(nwbfile, nex_file_name):
    file_data = nexfile.Reader(useNumpy=True).ReadNexFile(nex_file_name)
    file_header = file_data['FileHeader']  # dict of .nex file info
    writer_software = file_data['MetaData']['file']['writerSoftware']  # dict of name, version

    # first half of variables contains spike times, second half contains spike waveforms for each spike time
    num_vars = len(file_data['Variables'])
    print('adding ' + num_vars + ' units')
    start_var = round(num_vars / 2)  # read just the waveform variables

    # sanity checks
    if num_vars % 2 != 0:
        raise InconsistentInputException()

    for i in range(start_var, num_vars):
        var = file_data['Variables'][i]
        var_header = var['Header']
        var_ts_only = file_data['Variables'][i - start_var]
        if var_header['Type'] != 3:  # 3 = waveform
            raise UnsupportedInputException()
        if var_header['Units'] != 'mV':
            raise UnsupportedInputException()
        if var_header['TsDataType'] != 1:  # 1 = 64-bit integer
            raise UnsupportedInputException()
        if var_header['ADtoMV'] == 0:
            raise UnsupportedInputException()
        if (var_ts_only['Timestamps'] != var['Timestamps']).any():
            raise InconsistentInputException()
        if var['Timestamps'].shape != (var_header['Count'], ):
            raise InconsistentInputException()
        if var['WaveformValues'].shape != (var_header['Count'], var_header['NPointsWave']):
            raise InconsistentInputException()
        if var['WaveformValues'].shape != (var_header['Count'], var_header['NPointsWave']):
            raise InconsistentInputException()

    # var["Header"]["Type"] -- 3 - waveform
    # var["Header"]["Name"] -- variable name
    # var["Header"]["Version"] -- variable version in file
    # var["Header"]["Count"] -- number of waveforms
    # var["Header"]["TsDataType"] --
    #             if 0, timestamps are stored as 32-bit integers;
    #             if 1, timestamps are stored as 64-bit integers;
    #             supported by NeuroExplorer version 5.100 or greater
    # var["Header"]["ContDataType"] --
    #             if 0, waveform and continuous values are stored as 16-bit integers;
    #             if 1, waveform and continuous values are stored as 32-bit floating point values in units specified in
    #             Units field
    # var["Header"]["SamplingRate"] -- waveform sampling frequency in Hertz
    # var["Header"]["ADtoMV"] --
    #             coefficient to convert from A/D values stored in file to units.
    #             A/D values in fileData are already scaled to units.
    #             see formula below MVOffset below;
    # var["Header"]["MVOffset"] --
    #             this offset is used to convert A/D values stored in file to units:
    #             value_in_units = raw * ADtoUnitsCoefficient + UnitsOffset;
    #             A/D values in fileData are already scaled to units.
    # var["Header"]["NPointsWave"] -- number of data points in each waveform
    # var["Header"]["PreThrTime"] -- pre-threshold time in seconds
    #             if waveform timestamp in seconds is t,
    #             then the timestamp of the first point of waveform is t - PrethresholdTimeInSeconds

    # add these columns to unit table
    nwbfile.add_unit_column('name', 'name')
    nwbfile.add_unit_column('pre_threshold_samples', 'number of samples before threshold')
    nwbfile.add_unit_column('num_samples', 'number of samples for each spike waveform')
    nwbfile.add_unit_column('num_spikes', 'number of spikes')
    nwbfile.add_unit_column('sampling_rate', 'sampling rate')
    nwbfile.add_unit_column('nex_var_version', 'variable version in the NEX5 file')

    # since waveforms are not a 1:1 mapping per unit, use table indexing
    nwbfile.add_unit_column('waveforms', 'waveforms for each spike', index=True)

    for i in range(start_var, num_vars):
        var = file_data['Variables'][i]
        var_header = var['Header']
        nwbfile.add_unit(electrodes=(1,),
                         name=var_header['Name'],
                         spike_times=var['Timestamps'],
                         pre_threshold_samples=var_header['PreThrTime'],
                         num_samples=var_header['NPointsWave'],
                         num_spikes=var_header['Count'],
                         sampling_rate=var_header['SamplingRate'],
                         nex_var_version=var_header['Version'],
                         waveforms=var['WaveformValues'])

# ADD THE UNITS
add_units(nwbfile, sorted_spikes_nex5_file)

# Add behavior
# make a spatialseries timeseries (eye data)
# add trials (behavior)

# NOTES ON PROCESSED BEHAVIOR FILES
# - How are the time stamps aligned? Yoni aligns them using the first time the monkey blinks as the zero point
# - Email Yoni for specific details about electrode locations and spike sorting
# - 6 sessions of behavior
# - 1 and 2 are calibration on a different task with ~210 trials
# is auto is whether its automatic calibration or not - after processing we only use the auto data
# start_trial, end_trial and eyepos are self explanatory
# 3-6 real data sessions happen sequentially
# environment is either null(old) or new(garden)
# in future data sets the environments have different names
# so rename them to ''=old and 'new'=garden to be forwards compatible

# VARIABLES
# posdat = location
# tme = time
# eyepos = eye position
# raypos = place monkey is looking in VR
# events is encoded numerically
# ie. 1= pump on 200=success
# nlx eye data is just to check that alignment works
# it is the only source of eye data about what the monkey is doing during breaks
# frm = frame
# tmeray = timestamps of ray data
# dirdat = heading
# joystick is on same time series as position data 1x2 vector of 0 or 1

# IMPORTANT INFORMATION ABOUT NON CALIBRATION TRIALS
# THE ITI is 4 or 8 SECONDS - BUT IT BEGINS ONE SECOND AFTER THE END ENCODE IN SUCCESSFUL TRIALS
# THIS IS BECAUSE THE SUCCESSFUL TRIAL ALWAYS HAS ONE SECOND OF BANANA TIME
# MAKE SURE TO ACCOUNT FOR THIS EXTRA SECOND!!!!!
# *** THIS BUG IS FIXED IN SUBSEQUENT BUFFALO DATA SETS ***

# add eye behavior
#from pynwb import TimeSeries

#test_ts = TimeSeries(name='test_timeseries', data=eye_data, unit='m', timestamps=eye_timestamps)
#nwbfile.add_acquisition(test_ts)
# check units


# add physical behavior
# this will become a loop
# the task seems quite complicated
# how can all the task-relevant variables be represented efficiently?

# write NWB file to disk using NWBHDF5IO
out_file = './nwb_test.nwb'
with NWBHDF5IO(out_file, 'w') as io:
    print('Writing to file: ' + out_file)
    io.write(nwbfile)
    print(nwbfile)
