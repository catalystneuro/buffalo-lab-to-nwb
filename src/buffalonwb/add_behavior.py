import scipy
import scipy.io as spio
import numpy as np
from pynwb.behavior import Position, EyeTracking


def get_t0_behavior(behavior_file):
    """Get initial timestamp"""
    behavior_data = loadmat(behavior_file)
    t0_0 = behavior_data['nlxtme'][0] / 1000.
    t0_1 = behavior_data['behavior'][0]['start_trial'][0][0] / 1000.
    return min(t0_0, t0_1)


def add_behavior(nwbfile, behavior_file, metadata_behavior, t0):
    # The timestamps for behavior data, coming from .mat files, are in milliseconds
    # and should be transformed to seconds with / 1000

    print("adding behavior...")
    # process raw behavior
    behavior_data = loadmat(behavior_file)
    behavior_module = nwbfile.create_processing_module(
        name='behavior',
        description='preprocessed behavioral data'
    )
    # Player Position
    meta_pos = metadata_behavior['Position']
    pos = Position(name=meta_pos['name'])
    all_pos = np.atleast_1d([[], [], []]).T
    all_tme = []
    for iepoch in range(len(behavior_data["behavior"])):
        if 'posdat' in behavior_data['behavior'][iepoch]:
            epoch_data = behavior_data["behavior"][iepoch]
            all_pos = np.r_[all_pos, epoch_data['posdat']]
            all_tme = np.r_[all_tme, epoch_data['tme']]

    # Metadata for SpatialSeries stored in Position
    pos.create_spatial_series(
        name=meta_pos['spatial_series'][0]['name'],
        data=all_pos,
        reference_frame=meta_pos['spatial_series'][0]['reference_frame'],
        timestamps=all_tme / 1000. - t0,
        conversion=np.nan
    )
    behavior_module.add(pos)

    # nlx eye movements
    nlxeye = EyeTracking(name='EyeTracking')
    # metadata for SpatialSeries stored in EyeTracking
    meta_et = metadata_behavior['EyeTracking']
    tt = np.array(behavior_data["nlxtme"]) / 1000. - t0
    nlxeye.create_spatial_series(
        name=meta_et['spatial_series'][0]['name'],
        data=np.array(behavior_data["nlxeye"]).T,
        reference_frame=meta_et['spatial_series'][0]['reference_frame'],
        rate=(tt[-1] - tt[0]) / len(tt),
        starting_time=tt[0],
        #timestamps=np.array(behavior_data["nlxtme"]) / 1000. - t0,
        conversion=np.nan
    )
    behavior_module.add(nlxeye)

    # trial columns
    nwbfile.add_trial_column(
        name='environment',
        description='trial environment (calibration if calibration trial)'
    )
    # nwbfile.add_trial_column(name='trial_vars', description='trial variables - different between calibration and task')

    # event key dictionary
    event_dict = {"new_trial": 1000,
                  "right_trial": 1001,
                  "left_trial": 1002,
                  "reward_on": 1,
                  "reward_off": 0,
                  "end_trial": 100,
                  "end_presentation": 101,
                  "successful_trial": 200}

    # process behavior here
    for iepoch in range(len(behavior_data["behavior"])):
        epoch_data = behavior_data["behavior"][iepoch]
        if iepoch < 2:
            process_behavior_calibration(nwbfile, iepoch + 1, epoch_data, t0)
        else:
            banana_flag = 1
            process_behavior(nwbfile, iepoch + 1, epoch_data, banana_flag, event_dict, t0)


# https://stackoverflow.com/questions/7008608/scipy-io-loadmat-nested-structures-i-e-dictionaries
def loadmat(filename):
    '''
    this function should be called instead of direct spio.loadmat
    as it cures the problem of not properly recovering python dictionaries
    from mat files. It calls the function check keys to cure all entries
    which are still mat-objects
    '''

    def _check_keys(d):
        '''
        checks if entries in dictionary are mat-objects. If yes
        todict is called to change them to nested dictionaries
        '''
        for key in d:
            if isinstance(d[key], spio.matlab.mio5_params.mat_struct):
                d[key] = _todict(d[key])
            if key == "behavior":
                d[key] = _tolist(d[key])
        return d

    def _todict(matobj):
        '''
        A recursive function which constructs from matobjects nested dictionaries
        '''
        d = {}
        for strg in matobj._fieldnames:
            elem = matobj.__dict__[strg]
            if isinstance(elem, spio.matlab.mio5_params.mat_struct):
                d[strg] = _todict(elem)
            elif isinstance(elem, np.ndarray):
                d[strg] = _tolist(elem)
            else:
                d[strg] = elem
        return d

    def _tolist(ndarray):
        '''
        A recursive function which constructs lists from cellarrays
        (which are loaded as numpy ndarrays), recursing into the elements
        if they contain matobjects.
        '''
        elem_list = []
        for sub_elem in ndarray:
            if isinstance(sub_elem, spio.matlab.mio5_params.mat_struct):
                elem_list.append(_todict(sub_elem))
            elif isinstance(sub_elem, np.ndarray):
                elem_list.append(_tolist(sub_elem))
            else:
                elem_list.append(sub_elem)
        return elem_list

    data = scipy.io.loadmat(filename, struct_as_record=False, squeeze_me=True)
    return _check_keys(data)


# BEHAVIOR FUNCTIONS
# def add_trial_columns():

def process_behavior_calibration(nwbfile, session, data, t0):
    # convert to floats
    # add calibration trials (session 1 & 2 )
    # no time series data, everything is inside trials
    num_trials = len(data["start_trial"])
    for t in range(num_trials):
        # add rest of calibration stuff
        trial_data = data["is_auto"][t]
        nwbfile.add_trial(start_time=float(data["start_trial"][t][0]) / 1000. - t0,
                          stop_time=float(data["end_trial"][t][0]) / 1000. - t0,
                          environment="calibration")  # ,
        # trial_vars=trial_data)
    nwbfile.add_epoch(start_time=float(data["start_trial"][0][0]) / 1000. - t0,
                      stop_time=float(data["end_trial"][num_trials - 1][0]) / 1000. - t0,
                      tags=["session: " + str(session), "envronment: calibraton"],
                      timeseries=[])


def process_behavior(nwbfile, session, data, banana_flag, event_dict, t0):
    #

    # process events to time stamps
    start_trial, end_trial, end_presentation, reward_on, reward_off, reward_data, reward_ts, success, right_trial, left_trial = process_events(
        [x[3] for x in data["events"]], [x[0] for x in data["events"]], event_dict)

    # add trial variables to trial_vars
    trial_data = dict()
    succesful_trial = list()
    num_trials = len(start_trial)
    for t in range(num_trials):
        succesful_trial.append(any((x > start_trial[t] and x < end_trial[t]) for x in success))
    trial_data["succesful_trial"] = succesful_trial
    trial_data["left_trial"] = left_trial
    trial_data["right_trial"] = right_trial

    # handling inconsistencies
    if banana_flag == 1:
        if data["env"] == 'New':
            data["env"] = 'Garden'
        elif not len(data["env"]):
            data["env"] = 'Old'
        for t in range(num_trials):
            if succesful_trial[t] == 1:
                # THIS IS BANANA TIME
                end_trial[t] = end_trial[t] + 1000

    # add time series
    # reward_ts = TimeSeries(name="reward_ts",data=reward_data, timestamps=reward_ts)
    # nwbfile.add_acquisition(reward_ts)

    # add trials and epoch
    for t in range(num_trials):
        nwbfile.add_trial(start_time=start_trial[t] / 1000. - t0,
                          stop_time=end_trial[t] / 1000. - t0,
                          environment=data["env"])  # , trial_vars=trial_data)

    nwbfile.add_epoch(start_time=start_trial[0] / 1000. - t0,
                      stop_time=end_trial[num_trials - 1] / 1000. - t0,
                      tags=['session: ' + str(session), 'envronment: ' + data["env"]],
                      timeseries=[])


def process_events(events, events_ts, event_dict):
    # get events and time stamps and return timestamps of events
    # check input for invalid trial keys
    # input checking on left and right trials
    # check number of trials
    start_trial = list_comp(events, events_ts, event_dict["new_trial"])
    end_trial = list_comp(events, events_ts, event_dict["end_trial"])
    if len(start_trial)>len(end_trial):
        print( "warning, number of start trials " + str(len(start_trial)) + " not equal to number of end trials " + str(len(end_trial)))
        start_trial=start_trial[1:len(end_trial)]

    end_presentation = list_comp(events, events_ts, event_dict["end_presentation"])
    reward_on = list_comp(events, events_ts, event_dict["reward_on"])
    reward_off = list_comp(events, events_ts, event_dict["reward_off"])
    reward_data = list()
    reward_ts = list()
    for e in range(0, len(events)):
        if events[e] == float(event_dict["reward_on"]):
            reward_data.append(1)
            reward_ts.append(events_ts[e])
        elif events[e] == float(event_dict["reward_off"]):
            reward_data.append(0)
            reward_ts.append(events_ts[e])
    # is right trial the opposite of left trial
    right_trial = list_comp(events, events_ts, event_dict["right_trial"])
    left_trial = list_comp(events, events_ts, event_dict["left_trial"])
    success = list_comp(events, events_ts, event_dict["successful_trial"])
    return start_trial, end_trial, end_presentation, reward_on, reward_off, reward_data, reward_ts, success, right_trial, left_trial


def list_comp(data, events_ts, key):
    idx = [i for i, x in enumerate(data) if x == key]
    ts = [events_ts[i] for i in idx]
    return ts
