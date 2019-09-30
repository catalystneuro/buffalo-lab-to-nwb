# Buffalo-lab-data-to-nwb
Scripts which convert Buffalo lab data to NWB format. Currently we only support conversion for processed data.

authors: Maija Honig, Ryan Ly, Ben Dichter, Luiz Tauffer

## Install

```
pip install git+https://github.com/ben-dichter-consulting/buffalo-lab-data-to-nwb.git
```

# Use
The conversion function can be used in different forms:

**1. Imported and run from a python script:** <br/>
Here's an example: we'll grab the data from the same experiment but stored in different `.npz` files and save it to a single `.nwb` file.
```python
from buffalonwb.conversion_module import conversion_function

source_paths = {}
source_paths['raw Nlx'] = {'type': 'dir', 'path': PATH_TO_DIR}
source_paths['processed Nlx'] = {'type': 'dir', 'path': PATH_TO_DIR}
source_paths['processed behavior'] = {'type': 'file', 'path': PATH_TO_FILE}
source_paths['sorted spikes'] = {'type': 'file', 'path': PATH_TO_FILE}

f_nwb = 'buffalo.nwb'
metafile = 'metafile.yml'

conversion_function(source_paths=source_paths,
                    f_nwb=f_nwb,
                    metafile=metafile,
                    skip_raw=True,
                    skip_processed=False,
                    lfp_iterator_flag=True,
                    no_copy=True)
```
<br/>

**2. Command line:** <br/>
Similarly, the conversion function can be called from the command line in terminal:
```
$ python conversion_module.py [raw_nlx_dir] [lfp_mat_dir]
  [sorted_spikes_nex5_file] [behavior_file] [output_file] [metadata_file]
  [-skipraw] [-skipprocessed] [-lfpiterator] [-dontcopy]
```

> IMPORTANT:  <br/>
> [raw_nlx_dir] and [lfp_mat_dir] should be paths to directories  <br/>
> [sorted_spikes_nex5_file] [behavior_file] [output_file] [metadata_file] should be paths to files  <br/>
>
> optional inputs
> add these after the positional arguments to use additional options <br/>
> "-skipraw" (will skip adding raw data to nwb file) <br/>
> "-skipprocessed" (will skip adding processed data to nwb file) <br/>
> "-lfpiterator" (change lfp data method to dataChunkIterator (for large data)) <br/>
> "-dontcopy" (ignore broken copy method by going straight to output file) <br/>

<br/>

**3. Graphical User Interface:** <br/>
To use the GUI, just run the auxiliary function `nwb_gui.py` from terminal:
```
$ python nwb_gui.py
```
