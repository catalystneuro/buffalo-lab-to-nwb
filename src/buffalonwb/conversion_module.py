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
import os
import glob
from natsort import natsorted


def conversion_function(source_paths, f_nwb, metafile, skip_raw=True, skip_processed=False,
                        lfp_iterator_flag=True, no_copy=True):
    """
    Main function for conversion from Buffalo's lab data to NWB.

    Parameters
    ----------
    source_paths : dict
        Dictionary with paths to source files/directories. e.g.:
        {'raw Nlx': {'type': 'dir', 'path': ''},
         'processed Nlx': {'type': 'dir', 'path': ''},
         'sorted spikes',: {'type': 'file', 'path': ''},
         'processed behavior': {'type': 'file', 'path': ''}}
    f_nwb : str
        Stem to output file. Two files might be produced using this stem:
        'f_nwb_raw.nwb' and 'f_nwb_processed.nwb'
    metafile : str or path
        Yaml metadata file.
    """

    # Source files
    raw_nlx_path = None
    lfp_mat_path = None
    behavior_file = None
    sorted_spikes_nex5_file = None
    for k, v in source_paths.items():
        if source_paths[k]['path'] != '':
            if k == 'raw Nlx':
                raw_nlx_path = Path(source_paths[k]['path'])
            if k == 'processed Nlx':
                lfp_mat_path = Path(source_paths[k]['path'])
            if k == 'processed behavior':
                behavior_file = Path(source_paths[k]['path'])
            if k == 'sorted spikes':
                sorted_spikes_nex5_file = Path(source_paths[k]['path'])

    # Output files
    nwbpath = Path(f_nwb).parent
    out_file_raw = str(nwbpath.joinpath(Path(f_nwb).stem + '_raw.nwb'))
    out_file_processed = str(nwbpath.joinpath(Path(f_nwb).stem + '_processed.nwb'))

    # Load metadata from YAML file
    with open(metafile) as f:
        metadata = yaml.safe_load(f)

    # Number of electrodes
    electrode_labels = natsorted([os.path.split(x)[1][:-4]
                                  for x in glob.glob(os.path.join(raw_nlx_path, 'CSC*.ncs'))
                                  if '_' not in os.path.split(x)[1]])

    # Check if timestamps_reference_time was given in metadata
    if "timestamps_reference_time" not in metadata:
        timezone = pytz.timezone('US/Pacific')
        metadata["timestamps_reference_time"] = timezone.localize(datetime.now())

    # MAKE NWB FILE
    nwbfile = NWBFile(**metadata['NWBFile'])

    electrode_table_region = add_electrodes(
        nwbfile=nwbfile,
        metadata_ecephys=metadata['Ecephys'],
        num_electrodes=len(electrode_labels),
        electrode_labels=electrode_labels
    )

    if skip_raw:
        print("skipping raw data...")
    if not skip_raw:
        # Raw data
        add_raw_nlx_data(
            nwbfile=nwbfile,
            raw_nlx_path=raw_nlx_path,
            electrode_table_region=electrode_table_region,
            num_electrodes=len(electrode_labels)
        )

        # Write raw
        with NWBHDF5IO(out_file_raw, mode='w') as io:
            print('Writing to file: ' + out_file_raw)
            io.write(nwbfile)
            print(nwbfile)

    if skip_processed:
        print("skipping processed data...")
    if not skip_processed:
        if no_copy or skip_raw:
            nwbfile_proc = nwbfile
        else:
            # copy from raw to maintain file linkage
            raw_io = NWBHDF5IO(out_file_raw, mode='r')
            raw_nwbfile_in = raw_io.read()
            nwbfile_proc = raw_nwbfile_in.copy()
            electrode_table_region = nwbfile_proc.acquisition['raw_ephys'].electrodes
            print('Copying NWB file ' + out_file_raw)

        # BEHAVIOR (PROCESSED)
        if behavior_file is not None:
            add_behavior(
                nwbfile=nwbfile_proc,
                behavior_file=str(behavior_file),
                metadata_behavior=metadata['Behavior']
            )

        # PROCESSED COMPONENTS
        # UNITS
        if sorted_spikes_nex5_file is not None:
            add_units(
                nwbfile=nwbfile_proc,
                nex_file_name=sorted_spikes_nex5_file
            )

        # LFP
        if lfp_mat_path is not None:
            add_lfp(
                nwbfile=nwbfile_proc,
                lfp_path=lfp_mat_path,
                electrodes=electrode_table_region,
                iterator_flag=lfp_iterator_flag,
                all_electrode_labels=electrode_labels
            )

        # WRITE PROCESSED
        if no_copy or skip_raw:
            with NWBHDF5IO(out_file_processed, mode='w') as io:
                print('Writing to file: ' + out_file_processed)
                io.write(nwbfile_proc)
                print(nwbfile)
        else:
            with NWBHDF5IO(out_file_processed, mode='w', manager=raw_io.manager) as io:
                print('Writing to file: ' + out_file_processed)
                io.write(nwbfile_proc)
                print(nwbfile)
        if 'raw_io' in locals():
            raw_io.close()


def add_electrodes(nwbfile, metadata_ecephys, num_electrodes, electrode_labels=None):
    # Add device
    device = nwbfile.create_device(name=metadata_ecephys['Device']['name'])

    # Add electrodes
    metadata_eg = metadata_ecephys['ElectrodeGroup']
    electrode_group = nwbfile.create_electrode_group(
        name=metadata_eg['name'],
        description=metadata_eg['description'],
        location=metadata_eg['location'],
        device=device
    )

    if electrode_labels:
        nwbfile.add_electrode_column('label', 'labels of electrodes')

    for i in range(num_electrodes):
        kwargs = dict()
        if electrode_labels:
            kwargs.update(label=electrode_labels[i])

        nwbfile.add_electrode(
            x=math.nan,
            y=math.nan,
            z=math.nan,
            imp=math.nan,
            location=electrode_group.location,
            filtering='none',
            group=electrode_group,
            id=i + 1,
            **kwargs
        )

    # all electrodes in table region
    electrode_table_region = nwbfile.create_electrode_table_region(
        region=list(range(0, num_electrodes)),
        description='all the electrodes'
    )

    return electrode_table_region


# If called from terminal
if __name__ == '__main__':
    """
    Usage: python conversion_module.py [raw_nlx_dir] [lfp_mat_dir]
    [sorted_spikes_nex5_file] [behavior_file] [output_file] [metadata_file]
    [-skipraw] [-skipprocessed] [-lfpiterator] [-dontcopy]
    """
    import sys

    source_paths = {
        'raw Nlx': {'type': 'dir', 'path': sys.argv[1]},
        'processed Nlx': {'type': 'dir', 'path': sys.argv[2]},
        'sorted spikes': {'type': 'file', 'path': sys.argv[3]},
        'processed behavior': {'type': 'file', 'path': sys.argv[4]}
    }

    f_nwb = sys.argv[5]
    metafile = sys.argv[6]

    skip_raw = any([i == '-skipraw' for i in sys.argv])
    skip_processed = any([i == '-skipprocessed' for i in sys.argv])
    lfp_iterator_flag = any([i == '-lfpiterator' for i in sys.argv])
    no_copy = any([i == '-dontcopy' for i in sys.argv])

    conversion_function(source_paths=source_paths,
                        f_nwb=f_nwb,
                        metafile=metafile,
                        skip_raw=skip_raw,
                        skip_processed=skip_processed,
                        lfp_iterator_flag=lfp_iterator_flag,
                        no_copy=no_copy)
