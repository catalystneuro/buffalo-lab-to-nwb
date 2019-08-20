# Buffalo-lab-data-to-nwb
Scripts which convert Buffalo lab data to NWB format. Currently we only support conversion for processed data.

authors: Maija Honig, Ryan Ly, Ben Dichter

## Install

```
pip install git+https://github.com/ben-dichter-consulting/buffalo-lab-data-to-nwb.git
```

## Usage

```
python nwb.py [metadata_file] [lfp_mat_file] [sorted_spikes_nex5_file] [behavior_eye_file] [raw_nlx_file] [optional options]

# optional inputs
# add these after the positional arguments to use additional options
# "-skipraw" (will skip adding raw data to nwb file)
# "-skipprocessed" (will skip adding processed data to nwb file)
# "-lfpiterator" (change lfp data method to dataChunkIterator (for large data))
# "-dontcopy" (ignore broken copy method by going straight to output file)
```
