from pynwb import NWBHDF5IO, NWBFile

from buffalonwb import __version__
from buffalonwb.add_units import add_units
from buffalonwb.add_raw_nlx_data import add_raw_nlx_data
from buffalonwb.add_behavior import add_behavior
from buffalonwb.add_processed_nlx_data import add_lfp

from datetime import datetime
from pathlib import Path
import ruamel.yaml as yaml
import pytz
import math
import os
import argparse
import glob
from natsort import natsorted


def conversion_function(source_paths, f_nwb, metafile, skip_raw, skip_processed, lfp_iterator_flag, no_copy):
    """
    Main function for conversion from Buffalo's lab data formats to NWB.

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

    # parse filename of behavior mat file for session_start_time, localize to Pacific time for Buffalo Lab
    session_start_time = datetime.strptime(behavior_file.stem[8:], '%Y-%m-%d_%H-%M-%S')
    session_start_time = pytz.timezone('US/Pacific').localize(session_start_time)
    metadata['NWBFile']['session_start_time'] = session_start_time

    # build NWB file
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
        # Add raw data
        add_raw_nlx_data(
            nwbfile=nwbfile,
            raw_nlx_path=raw_nlx_path,
            electrode_table_region=electrode_table_region,
            num_electrodes=len(electrode_labels)
        )

        # Write raw data to NWB file
        print('Writing to file: ' + out_file_raw)
        with NWBHDF5IO(out_file_raw, mode='w') as io:
            io.write(nwbfile)
        print(nwbfile)

    if skip_processed:
        print("skipping processed data...")
    if not skip_processed:
        if no_copy or skip_raw:
            nwbfile_proc = nwbfile
        else:
            # Copy from raw data NWB file to maintain file linkage
            print('copying NWB file ' + out_file_raw)
            raw_io = NWBHDF5IO(out_file_raw, mode='r')
            raw_nwbfile_in = raw_io.read()
            nwbfile_proc = raw_nwbfile_in.copy()
            electrode_table_region = nwbfile_proc.acquisition['raw_ephys'].electrodes

        # Add processed behavior data
        if behavior_file is not None:
            add_behavior(
                nwbfile=nwbfile_proc,
                behavior_file=str(behavior_file),
                metadata_behavior=metadata['Behavior']
            )

        # Add sorted units
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

        # Write processed data to NWB file
        print('Writing to file: ' + out_file_processed)
        if no_copy or skip_raw:
            with NWBHDF5IO(out_file_processed, mode='w') as io:
                io.write(nwbfile_proc)
        else:
            with NWBHDF5IO(out_file_processed, mode='w', manager=raw_io.manager) as io:
                io.write(nwbfile_proc)
            raw_io.close()

        print(nwbfile_proc)


def add_electrodes(nwbfile, metadata_ecephys, num_electrodes, electrode_labels=None):
    # Add device
    device = nwbfile.create_device(name=metadata_ecephys['Device']['name'])

    # Add electrode group -- assume only one
    metadata_eg = metadata_ecephys['ElectrodeGroup']
    if metadata_eg['device'] != device.name:
        raise Exception('Name of device in ElectrodeGroup must match the single Device name in the metadata YAML file')
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
            id=id,
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

    # Create an electrode table region encompassing all electrodes
    electrode_table_region = nwbfile.create_electrode_table_region(
        region=list(range(0, num_electrodes)),
        description='all the electrodes'
    )

    return electrode_table_region


# If called from terminal
if __name__ == '__main__':
    """
    Usage: python conversion_module.py [raw_nlx_dir] [processed_mat_dir]
    [sorted_spikes_nex5_file] [behavior_file] [metadata_file] [output_file]
    [-skipraw] [-skipprocessed] [-lfpiterator] [-dontcopy]
    """
    import sys

    parser = argparse.ArgumentParser("A package for converting Buffalo Lab data to the NWB standard.")
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
        help="Show the version, and exit.",
    )
    parser.add_argument(
        "raw_nlx_dir", help="The path to the directory holding raw Neuralynx CSC files."
    )
    parser.add_argument(
        "processed_mat_dir", help="The path to the directory holding processed .mat files."
    )
    parser.add_argument(
        "sorted_spikes_nex5_file", help="The path to the sorted spikes NEX5 file."
    )
    parser.add_argument(
        "behavior_mat_file", help="The path to the processed behavior MAT file."
    )
    parser.add_argument(
        "metadata_yaml_file", help="The path to the metadata YAML file."
    )
    parser.add_argument(
        "output_file", help="The stem of the output file to be created."
    )
    parser.add_argument(
        "--skipraw",
        action="store_false",
        default=True,
        help="Whether to skip adding the raw data to the NWB file",
    )
    parser.add_argument(
        "--skipprocessed",
        action="store_true",
        default=False,
        help="Whether to skip adding the processed data to the NWB file",
    )
    parser.add_argument(
        "--lfpiterator",
        action="store_false",
        default=True,
        help="Whether to use the LFP channel iterator",
    )
    parser.add_argument(
        "--dontcopy",
        action="store_false",
        default=True,
        help=("Whether to create a link between the processed data NWB file and the raw data NWB file instead of "
              "copying the raw data"),
    )

    if not sys.argv[1:]:
        args = parser.parse_args(["--help"])
    else:
        args = parser.parse_args()

    source_paths = {
        'raw Nlx': {'type': 'dir', 'path': args.raw_nlx_dir},
        'processed Nlx': {'type': 'dir', 'path': args.processed_mat_dir},
        'sorted spikes': {'type': 'file', 'path': args.sorted_spikes_nex5_file},
        'processed behavior': {'type': 'file', 'path': args.behavior_mat_file}
    }

    conversion_function(source_paths=source_paths,
                        f_nwb=args.output_file,
                        metafile=args.metadata_yaml_file,
                        skip_raw=args.skipraw,
                        skip_processed=args.skipprocessed,
                        lfp_iterator_flag=args.lfpiterator,
                        no_copy=args.dontcopy)
