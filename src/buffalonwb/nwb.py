# IMPORTING AND SETUP
# Currently copy/pasted


import numpy as np
from pynwb import TimeSeries
from pynwb.ecephys import ElectricalSeries
from hdmf.data_utils import DataChunkIterator
import h5py
# MAKE SETUP FILE
import sys
sys.path.insert(0,'C:\\Users\\Maija\\Documents\\NWB\\buffalo-lab-data-to-nwb\\src\\nexfile')
import nexfile
from uuid import UUID
from struct import unpack
from warnings import warn

from datetime import datetime
import pytz
from pynwb import NWBFile
from pynwb import ProcessingModule
import math
import os
from pynwb import NWBHDF5IO
import sys

from add_units import add_units
from add_raw_nlx_data import add_raw_nlx_data
from add_behavior import add_behavior
from add_processed_nlx_data import add_lfp
"""
Usage: python nwb.py [metadata_file] [lfp_mat_file] [sorted_spikes_nex5_file] [behavior_eye_file] [raw_nlx_file]

"""


def main():
    # main
    # FILENAMES
    # files for jupyter

    metadata_file = sys.argv[1] #'C:\\Users\\Maija\\Documents\\NWB\\buffalo-lab-data-to-nwb\\src\\buffalonwb\\dataset_information.txt'
    lfp_mat_file = sys.argv[2]#'C:\\Users\\Maija\\Documents\\NWB\\buffalo-data\\ProcessedNlxData\\2017-04-27_11-41-21\\CSC%_ex.mat'
    sorted_spikes_nex5_file = sys.argv[3]#'C:\\Users\\Maija\\Documents\\NWB\\buffalo-data\\SortedSpikes\\2017-04-27_11-41-21_sorted.nex5'
    behavior_eye_file = sys.argv[4] #'C:\\Users\\Maija\\Documents\\NWB\\buffalo-data\\ProcessedBehavior\\MatFile_2017-04-27_11-41-21.mat'
    raw_nlx_file = sys.argv[5] #'C:\\Users\\Maija\\Documents\\NWB\\buffalo-data\\RawCSCs\\CSC%.ncs'
    skip_raw = any([i == '-skipraw' for i in sys.argv])
    skip_processed = any([i == '-skipprocessed' for i in sys.argv])
    lfp_iterator_flag = any([i == '-lfpiterator' for i in sys.argv])
    no_copy = any([i == '-dontcopy' for i in sys.argv])

    out_file_raw = './buffalo_raw.nwb'
    out_file_processed = './buffalo_processed.nwb'

    # METADATA
    metadata = read_metadata(metadata_file)

    session_start_time = datetime.now()  # The first time recorded in the session ( I will get this)
    timestamps_reference_time = datetime.now()  # The reference time for timestamps - this is probably the same as session start time but pretty sure Yoni said it's the first blink
    timezone = pytz.timezone('US/Pacific')

    # ADD THE HEADER DATA HERE??
    # dump in labmetadata
    # https://pynwb.readthedocs.io/en/stable/pynwb.file.html#pynwb.file.LabMetaData
    # (buffalo_labmetadata)

    # MAKE NWB FILE
    # https://pynwb.readthedocs.io/en/stable/pynwb.file.html
    metadata["session_start_time"] = timezone.localize(session_start_time)
    metadata["timestamps_reference_time"] = timezone.localize(timestamps_reference_time)
    nwbfile = NWBFile(session_description=metadata["session_description"],
                      identifier=metadata["identifier"],
                      session_id=metadata["session_id"],
                      session_start_time=metadata["session_start_time"],
                      timestamps_reference_time=metadata["timestamps_reference_time"],
                      notes=metadata["notes"],
                      stimulus_notes=metadata["stimulus_notes"],
                      data_collection=metadata["data_collection"],
                      experiment_description=metadata["experiment_description"],
                      protocol=metadata["protocol"],
                      keywords=metadata["keywords"],
                      experimenter=metadata["experimenter"],
                      lab=metadata["lab"],
                      institution=metadata["institution"])
    electrode_table_region = add_electrodes(nwbfile, metadata)
    proc_module = nwbfile.create_processing_module('processed_data', 'module for processed data')

    if skip_raw:
        print("skipping raw data...")
    if not skip_raw:
        # RAW COMPONENTS
        # RAW DATA
        add_raw_nlx_data(nwbfile, raw_nlx_file, electrode_table_region, metadata["num_electrodes"])

        # BEHAVIOR (PROCESSED)
        add_behavior(nwbfile, behavior_eye_file)

        # WRITE RAW
        with NWBHDF5IO(out_file_raw, mode='w') as io:
            print('Writing to file: ' + out_file_raw)
            io.write(nwbfile)
            print(nwbfile)

    if skip_processed:
        print("skipping processed data...")
    if not skip_processed:
        if no_copy:
            nwbfile_proc = nwbfile
        else:
            #copy from raw to maintain file linkage
            raw_io = NWBHDF5IO(out_file_raw, 'r')
            raw_nwbfile_in = raw_io.read()
            nwbfile_proc = raw_nwbfile_in.copy()
            with NWBHDF5IO(out_file_raw, mode='r') as raw_io:
                raw_nwbfile_in = raw_io.read()
                nwbfile_proc = raw_nwbfile_in.copy()
            print('Copying NWB file ' + out_file_raw)


        # BEHAVIOR (PROCESSED)
        #add_behavior(nwbfile, behavior_eye_file)

        # PROCESSED COMPONENTS
        # UNITS
        # add_units(nwbfile_proc, sorted_spikes_nex5_file)
        add_units(nwbfile, sorted_spikes_nex5_file)

        # LFP
        add_lfp(nwbfile_proc,lfp_mat_file,electrode_table_region,metadata["num_electrodes"],proc_module,lfp_iterator_flag)
        #add_lfp(nwbfile, lfp_mat_file, electrode_table_region, 4, proc_module, iterator_flag)

        # WRITE PROCESSED
        if no_copy:
            with NWBHDF5IO(out_file_processed, mode='w') as io:
            # with NWBHDF5IO(out_file_processed, mode='w') as io:
                print('Writing to file: ' + out_file_processed)
                io.write(nwbfile)
                print(nwbfile)
        else:
            with NWBHDF5IO(out_file_processed, mode='w', manager=raw_io.manager) as io:
            # with NWBHDF5IO(out_file_processed, mode='w') as io:
                print('Writing to file: ' + out_file_processed)
                io.write(nwbfile)
                print(nwbfile)


# general tools
def read_metadata(metadata_file):
    d = {}
    with open(metadata_file) as f:
        for line in f:
            if '#' in line or not line.strip(): continue
            key, val = line.replace("\r", "").replace("\n", "").split("=")
            d[key] = val
    # manually convert keywords and num_electrodes to list and int respectively
    d["keywords"] = list(d["keywords"].split(","))
    d["num_electrodes"] = int(d["num_electrodes"])
    return d


def add_electrodes(nwbfile, metadata):
    # Add the device and electrodes
    # Add device
    # NWB needs to know what recording device we used before we can make any electrode groups
    device_name = metadata["device_name"]
    device = nwbfile.create_device(name=device_name)

    # Add electrodes
    # electrode groups each need a name, location and device
    eg_name = metadata["eg_name"]
    eg_description = metadata["eg_description"]
    eg_location = metadata["eg_description"]
    electrode_group = nwbfile.create_electrode_group(name=eg_name,
                                                     description=eg_description,
                                                     location=eg_location,
                                                     device=device)

    # electrodes each need an ID from 1-num_electrodes
    # https://pynwb.readthedocs.io/en/stable/pynwb.file.html#pynwb.file.NWBFile.add_electrode
    # we'll need to get the electrode information from Yoni
    num_electrodes = metadata["num_electrodes"]
    for id in range(1, num_electrodes + 1):
        nwbfile.add_electrode(x=math.nan,
                              y=math.nan,
                              z=math.nan,
                              imp=math.nan,
                              location=electrode_group.location,
                              filtering='none',
                              group=electrode_group,
                              id=id)

    # all electrodes in table region
    electrode_table_region = nwbfile.create_electrode_table_region(list(range(0, num_electrodes)), 'all the electrodes')

    return electrode_table_region

if __name__ == '__main__':
    main()
