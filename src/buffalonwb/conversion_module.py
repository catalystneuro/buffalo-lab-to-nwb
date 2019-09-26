from pynwb import NWBHDF5IO, NWBFile
from buffalonwb.add_units import add_units
from buffalonwb.add_raw_nlx_data import add_raw_nlx_data
from buffalonwb.add_behavior import add_behavior
from buffalonwb.add_processed_nlx_data import add_lfp

from datetime import datetime
from pathlib import Path
import yaml
import pytz
import math


def conversion_function(*f_sources, f_nwb, metafile, **kwargs):
    """
    Main function for conversion from Buffalo's lab data to NWB.

    Parameters
    ----------
    *f_sources : sequence of str
        Source files, in this order: lfp_mat_file, sorted_spikes_nex5_file,
        behavior_file, raw_nlx_file
    f_nwb : str
        Stem to output file. Two files might be produced using this stem:
        'f_nwb_raw.nwb' and 'f_nwb_processed.nwb'
    metadata_file : str or path
        Yaml metadata file.
    **kwargs :
        Optional boolean keyword arguments:
        skip_raw : boolean
        skip_processed : boolean
        lfp_iterator_flag : boolean,
        no_copy : boolean
    """

    # kwargs
    if 'skip_raw' not in kwargs:
        skip_raw = True
    if 'skip_processed' not in kwargs:
        skip_processed = False
    if 'lfp_iterator_flag' not in kwargs:
        lfp_iterator_flag = True
    if 'no_copy' not in kwargs:
        no_copy = True

    # Source files
    for i, f in enumerate(f_sources):
        if i == 0:
            lfp_mat_file = Path(f)
        elif i == 1:
            sorted_spikes_nex5_file = Path(f)
        elif i == 2:
            behavior_file = Path(f)
        elif i == 3:
            raw_nlx_file = Path(f)

    # Output files
    out_file_raw = f_nwb.stem + '_raw.nwb'
    out_file_processed = f_nwb.stem + '_processed.nwb'

    # Load metadata from YAML file
    with open(metafile) as f:
        metadata = yaml.safe_load(f)

    # The reference time for timestamps - this is probably the same as session start time but pretty sure Yoni said it's the first blink
    timestamps_reference_time = datetime.now()
    timezone = pytz.timezone('US/Pacific')

    # Number of electrodes
    nChannels = 124

    # MAKE NWB FILE
    metadata["session_start_time"] = timezone.localize(session_start_time)
    metadata["timestamps_reference_time"] = timezone.localize(timestamps_reference_time)
    nwbfile = NWBFile(session_description=metadata['NWBFile']["session_description"],
                      identifier=metadata['NWBFile']["identifier"],
                      session_id=metadata['NWBFile']["session_id"],
                      session_start_time=metadata['NWBFile']['session_start_time'],
                      timestamps_reference_time=timestamps_reference_time,
                      notes=metadata['NWBFile']["notes"],
                      stimulus_notes=metadata['NWBFile']["stimulus_notes"],
                      data_collection=metadata['NWBFile']["data_collection"],
                      experiment_description=metadata['NWBFile']["experiment_description"],
                      protocol=metadata['NWBFile']["protocol"],
                      keywords=metadata['NWBFile']["keywords"],
                      experimenter=metadata['NWBFile']["experimenter"],
                      lab=metadata['NWBFile']["lab"],
                      institution=metadata['NWBFile']["institution"])

    electrode_table_region = add_electrodes(
        nwbfile=nwbfile,
        metadata_ecephys=metadata['Ecephys'],
        num_electrodes=nChannels
    )
    proc_module = nwbfile.create_processing_module('Ecephys', 'module for processed data')

    if skip_raw:
        print("skipping raw data...")
    if not skip_raw:
        # RAW COMPONENTS
        # RAW DATA
        add_raw_nlx_data(
            nwbfile=nwbfile,
            raw_nlx_file=raw_nlx_file,
            electrode_table_region=electrode_table_region,
            num_electrodes=nChannels
        )

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
            # copy from raw to maintain file linkage
            raw_io = NWBHDF5IO(out_file_raw, mode='r')
            raw_nwbfile_in = raw_io.read()
            nwbfile_proc = raw_nwbfile_in.copy()
            print('Copying NWB file ' + out_file_raw)

        # BEHAVIOR (PROCESSED)
        if behavior_file is not None:
            add_behavior(
                nwbfile=nwbfile_proc,
                behavior_file=behavior_file,
                metadata_behavior=metadata['Behavior']
            )

        # PROCESSED COMPONENTS
        # UNITS
        if sorted_spikes_nex5_file is not None:
            add_units(nwbfile_proc, sorted_spikes_nex5_file)

        # LFP
        if lfp_mat_file is not None:
            add_lfp(
                nwbfile=nwbfile_proc,
                lfp_file_name=lfp_mat_file,
                electrode_table_region=electrode_table_region,
                num_electrodes=nChannels,
                proc_module=proc_module,
                iterator_flag=lfp_iterator_flag)

        # WRITE PROCESSED
        if no_copy:
            with NWBHDF5IO(out_file_processed, mode='w') as io:
                print('Writing to file: ' + out_file_processed)
                io.write(nwbfile)
                print(nwbfile)
        else:
            with NWBHDF5IO(out_file_processed, mode='w', manager=raw_io.manager) as io:
                print('Writing to file: ' + out_file_processed)
                io.write(nwbfile)
                print(nwbfile)
        if 'raw_io' in locals():
            del raw_io


# # general tools
# def read_metadata(metadata_file):
#     d = {}
#     with open(metadata_file) as f:
#         for line in f:
#             if '#' in line or not line.strip(): continue
#             key, val = line.replace("\r", "").replace("\n", "").split("=")
#             d[key] = val
#     # manually convert keywords and num_electrodes to list and int respectively
#     d["keywords"] = list(d["keywords"].split(","))
#     d["num_electrodes"] = int(d["num_electrodes"])
#     return d


def add_electrodes(nwbfile, metadata_ecephys, num_electrodes):
    # Add device
    device = nwbfile.create_device(name=metadata_ecephys['Device']['name'])

    # Add electrodes
    metadata_eg = metadata_ecephys['ElectrodeGroup']
    electrode_group = nwbfile.create_electrode_group(name=metadata_eg['name'],
                                                     description=metadata_eg['description'],
                                                     location=metadata_eg['location'],
                                                     device=device)

    for id in range(1, num_electrodes + 1):
        nwbfile.add_electrode(
            x=math.nan,
            y=math.nan,
            z=math.nan,
            imp=math.nan,
            location=electrode_group.location,
            filtering='none',
            group=electrode_group,
            id=id
        )

    # all electrodes in table region
    electrode_table_region = nwbfile.create_electrode_table_region(
        region=list(range(0, num_electrodes)),
        description='all the electrodes'
    )

    return electrode_table_region


if __name__ == '__main__':
    """
    Usage: python nwb.py [lfp_mat_file] [sorted_spikes_nex5_file] [behavior_file]
    [raw_nlx_file] [output_file] [metadata_file]
    """
    import sys

    f1 = sys.argv[1]
    f2 = sys.argv[2]
    f3 = sys.argv[3]
    f4 = sys.argv[4]
    f_nwb = sys.argv[5]
    metafile = sys.argv[6]
    conversion_function(f1, f2, f3, f4,
                        f_nwb=f_nwb,
                        metafile=metafile)

    # metadata_file = sys.argv[1] #'C:\\Users\\Maija\\Documents\\NWB\\buffalo-lab-data-to-nwb\\src\\buffalonwb\\dataset_information.txt'
    # lfp_mat_file = sys.argv[2]#'C:\\Users\\Maija\\Documents\\NWB\\buffalo-data\\ProcessedNlxData\\2017-04-27_11-41-21\\CSC%_ex.mat'
    # sorted_spikes_nex5_file = sys.argv[3]#'C:\\Users\\Maija\\Documents\\NWB\\buffalo-data\\SortedSpikes\\2017-04-27_11-41-21_sorted.nex5'
    # behavior_file = sys.argv[4] #'C:\\Users\\Maija\\Documents\\NWB\\buffalo-data\\ProcessedBehavior\\MatFile_2017-04-27_11-41-21.mat'
    # raw_nlx_file = sys.argv[5] #'C:\\Users\\Maija\\Documents\\NWB\\buffalo-data\\RawCSCs\\CSC%.ncs'
    # skip_raw = any([i == '-skipraw' for i in sys.argv])
    # skip_processed = any([i == '-skipprocessed' for i in sys.argv])
    # lfp_iterator_flag = any([i == '-lfpiterator' for i in sys.argv])
    # no_copy = any([i == '-dontcopy' for i in sys.argv])
    #
    # main(metadata_file, lfp_mat_file, sorted_spikes_nex5_file, behavior_file,
    #      raw_nlx_file, skip_raw, skip_processed, lfp_iterator_flag, no_copy)
