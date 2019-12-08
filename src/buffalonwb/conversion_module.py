from pynwb import NWBHDF5IO, NWBFile

from buffalonwb import __version__
from buffalonwb.add_raw_nlx_data import add_raw_nlx_data, get_csc_file_header_info
from buffalonwb.add_units import add_units, get_t0_nex5
from buffalonwb.add_behavior import add_behavior, get_t0_behavior
from buffalonwb.add_processed_nlx_data import add_lfp
from nexfile import nexfile

from natsort import natsorted
from pathlib import Path
import numpy as np
import ruamel.yaml as yaml
import pytz
import math
import argparse


def conversion_function(source_paths, f_nwb, metadata, skip_raw, skip_processed, no_lfp_iterator):
    """
    Main function for conversion of Buffalo lab data from Neuralynx/Matlab/Neuroexplorer formats to NWB.

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
    metadata : dict
        Metadata dictionary.
    skip_raw : bool
        Whether to skip adding raw data to the file.
    skip_processed : bool
        Whether to skip adding processed data to the file.
    no_lfp_iterator : bool
        Whether to not use a data chunk iterator over channels for the LFP data.

    """

    # Source files
    raw_nlx_path, lfp_mat_path, behavior_file, sorted_spikes_nex5_file = check_source_paths(source_paths)
    if raw_nlx_path is None:
        raise ValueError('Raw NLX file is required for getting the nub: %s' % sorted_spikes_nex5_file)

    # Output files
    nwbpath = Path(f_nwb).parent
    out_file_raw = str(nwbpath.joinpath(Path(f_nwb).stem + '_raw.nwb'))
    out_file_processed = str(nwbpath.joinpath(Path(f_nwb).stem + '_processed.nwb'))

    # Get electrode labels from raw nlx directory file names
    electrode_labels = natsorted([x.stem for x in raw_nlx_path.glob('CSC*.ncs') if '_' not in x.stem])

    # localize session start time to Pacific time for Buffalo Lab
    # Get session_start_time from CSC 'TimeCreated' field, it does not contain Milliseconds
    header = get_csc_file_header_info(raw_nlx_path=raw_nlx_path)
    metadata['NWBFile']['session_start_time'] = pytz.timezone('US/Pacific').localize(
        header['TimeCreated']
    )

    if skip_raw:
        print("Skipping raw data...")
    if not skip_raw:
        # Build NWB file
        nwb_raw = NWBFile(**metadata['NWBFile'])

        # Add device and electrodes based on given metadata and electrode labels
        electrode_table_region = add_electrodes(
            nwbfile=nwb_raw,
            metadata_ecephys=metadata['Ecephys'],
            num_electrodes=len(electrode_labels),
            electrode_labels=electrode_labels
        )

        # Add raw data
        add_raw_nlx_data(
            nwbfile=nwb_raw,
            raw_nlx_path=raw_nlx_path,
            electrode_table_region=electrode_table_region,
        )

        # Write raw data to NWB file
        print('Writing to file: ' + out_file_raw)
        with NWBHDF5IO(out_file_raw, mode='w') as io:
            io.write(nwb_raw)
        print(nwb_raw)

    if skip_processed:
        print("Skipping processed data...")
    else:
        # Build NWB file
        nwb_proc = NWBFile(**metadata['NWBFile'])

        # Add device and electrodes based on given metadata and electrode labels
        electrode_table_region = add_electrodes(
            nwbfile=nwb_proc,
            metadata_ecephys=metadata['Ecephys'],
            num_electrodes=len(electrode_labels),
            electrode_labels=electrode_labels
        )

        # Get reference time for t0
        t0 = np.Inf
        if sorted_spikes_nex5_file is not None:
            t0 = min(t0, get_t0_nex5(sorted_spikes_nex5_file))
        if behavior_file is not None:
            t0 = min(t0, get_t0_behavior(behavior_file))

        # Add sorted units
        if sorted_spikes_nex5_file is not None:
            add_units(
                nwbfile=nwb_proc,
                nex_file_name=sorted_spikes_nex5_file,
                t0=t0
            )

        # Add processed behavior data
        if behavior_file is not None:
            add_behavior(
                nwbfile=nwb_proc,
                behavior_file=str(behavior_file),
                metadata_behavior=metadata['Behavior'],
                t0=t0
            )

        # Add LFP
        if lfp_mat_path is not None:
            add_lfp(
                nwbfile=nwb_proc,
                lfp_path=lfp_mat_path,
                electrodes=electrode_table_region,
                iterator_flag=not no_lfp_iterator,
                all_electrode_labels=electrode_labels,
            )

        # Write processed data to NWB file
        print('Writing to file: ' + out_file_processed)
        with NWBHDF5IO(out_file_processed, mode='w') as io:
            io.write(nwb_proc)


def check_source_paths(source_paths):
    key = 'raw Nlx'
    raw_nlx_path = None
    if key in source_paths and source_paths[key]['path'] != '':
        raw_nlx_path = Path(source_paths[key]['path'])
        if not raw_nlx_path.is_dir():
            raise ValueError('Raw NLX path should be a directory: %s' % raw_nlx_path)

    key = 'processed Nlx'
    lfp_mat_path = None
    if key in source_paths and source_paths[key]['path'] != '':
        lfp_mat_path = Path(source_paths[key]['path'])
        if not lfp_mat_path.is_dir():
            raise ValueError('Processed NLX path should be a directory: %s' % lfp_mat_path)

    key = 'processed behavior'
    behavior_file = None
    if key in source_paths and source_paths[key]['path'] != '':
        behavior_file = Path(source_paths[key]['path'])
        if not behavior_file.is_file():
            raise ValueError('Behavior file must be a file: %s' % behavior_file)
        if behavior_file.suffix != ".mat":
            raise ValueError('Behavior file name must end with .mat: %s' % behavior_file)

    key = 'sorted spikes'
    sorted_spikes_nex5_file = None
    if key in source_paths and source_paths[key]['path'] != '':
        sorted_spikes_nex5_file = Path(source_paths[key]['path'])
        if not sorted_spikes_nex5_file.is_file():
            raise ValueError('Sorted spikes file must be a file: %s' % sorted_spikes_nex5_file)
        if sorted_spikes_nex5_file.suffix != ".nex5":
            raise ValueError('Sorted spikes file name must end with .nex5: %s' % sorted_spikes_nex5_file)

    return raw_nlx_path, lfp_mat_path, behavior_file, sorted_spikes_nex5_file


def add_electrodes(nwbfile, metadata_ecephys, num_electrodes, electrode_labels=None):
        # Add electrode groups
    metadata_eg = metadata_ecephys['ElectrodeGroup']
    for eg in metadata_eg:
        if eg['device'] not in nwbfile.devices:
            device = nwbfile.create_device(name=eg['device'])
        else:
            device = nwbfile.devices[eg['device']]
        electrode_group = nwbfile.create_electrode_group(
            name=eg['name'],
            description=eg['description'],
            location=eg['location'],
            device=device
        )

    if electrode_labels:
        nwbfile.add_electrode_column('label', 'labels of electrodes')

    for i in range(num_electrodes):
        kwargs = dict()
        if electrode_labels:
            kwargs.update(label=electrode_labels[i])

        nwbfile.add_electrode(
            id=i + 1,
            x=math.nan,
            y=math.nan,
            z=math.nan,
            imp=math.nan,
            location=electrode_group.location,
            filtering='none',
            group=electrode_group,
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
        action="store_true",
        default=False,
        help="Whether to skip adding the raw data to the NWB file",
    )
    parser.add_argument(
        "--skipprocessed",
        action="store_true",
        default=False,
        help="Whether to skip adding the processed data to the NWB file",
    )
    parser.add_argument(
        "--nolfpiterator",
        action="store_true",
        default=False,
        help="Whether to use the LFP channel iterator",
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
                        no_lfp_iterator=args.nolfpiterator)
