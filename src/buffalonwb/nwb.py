import sys
import pytz
import math
from datetime import datetime
from pprint import pprint
from nexfile import nexfile
from pynwb import NWBFile, NWBHDF5IO
from exceptions import InconsistentInputException, UnsupportedInputException
from read_sorted_spikes import add_units


"""
Usage: python nwb.py [lfp_mat_file] [sorted_spikes_nex5_file] [behavior_eye_file]

"""



def main():
    # create the NWBFile instance
    identifier = 'ADDME'

    session_description = 'ADDME'
    session_id = 'ADDME'
    session_start_time = datetime.now()  # 'ADDME'
    timestamps_reference_time = datetime.now()  # 'ADDME'
    timezone = pytz.timezone('US/Pacific')
    notes = 'ADDME'
    stimulus_notes = 'ADDME'

    data_collection = 'ADDME'  # notes about data collection and analyis
    experiment_description = 'ADDME'
    protocol = 'ADDME'
    keywords = ['ADDME']

    experimenter = 'Yoni Browning'
    lab = 'Buffalo Lab'
    institution = 'University of Washington'

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

    # create recording device
    device_name = 'Neuralynx ADDME'
    device = nwbfile.create_device(name=device_name)

    # create electrode group
    eg_name = 'Gray Matter Array ADDME'
    eg_description = 'ADDME'
    eg_location = 'Hippocampus ADDME'
    eg_device = device
    electrode_group = nwbfile.create_electrode_group(name=eg_name,
                                                     description=eg_description,
                                                     location=eg_location,
                                                     device=device)

    # add electrodes with id's 1 to num_electrodes, inclusive
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

    add_units(nwbfile, sys.argv[2])

    # write NWB file to disk
    out_file = './output/nwb_test.nwb'
    with NWBHDF5IO(out_file, 'w') as io:
        print('Writing to file: ' + out_file)
        io.write(nwbfile)
        print(nwbfile)


if __name__ == '__main__':
    main()
