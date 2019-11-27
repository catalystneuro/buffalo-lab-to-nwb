# Buffalo-lab-data-to-nwb
Scripts which convert Buffalo lab data to NWB format. Currently we only support conversion for processed data.

authors: Luiz Tauffer, Maija Honig, Ryan Ly, Ben Dichter

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
import yaml

source_paths = dict()
source_paths['raw Nlx'] = {'type': 'dir', 'path': PATH_TO_DIR}
source_paths['processed Nlx'] = {'type': 'dir', 'path': PATH_TO_DIR}
source_paths['processed behavior'] = {'type': 'file', 'path': PATH_TO_FILE}
source_paths['sorted spikes'] = {'type': 'file', 'path': PATH_TO_FILE}

# Output .nwb file
f_nwb = 'buffalo.nwb'

# Load metadata from YAML file
metafile = 'metafile.yml'
with open(metafile) as f:
    metadata = yaml.safe_load(f)

kwargs_fields = {
    'skip_raw': True,
    'skip_processed': False,
    'no_lfp_iterator': False,
}

conversion_function(source_paths=source_paths,
                    f_nwb=f_nwb,
                    metadata=metadata,
                    **kwargs_fields)

```
<br/>

**2. Command line:** <br/>
Similarly, the conversion function can be called from the command line in terminal:
```
$ python conversion_module.py [raw_nlx_dir] [lfp_mat_dir]
  [sorted_spikes_nex5_file] [behavior_file] [output_file] [metadata_file]
  [-skipraw] [-skipprocessed] [-lfpiterator]
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

<br/>

**3. Graphical User Interface:** <br/>
To use the GUI, just run the auxiliary function `nwb_gui.py` from terminal:
```
$ python nwb_gui.py
```
The GUI eases the task of editing the metadata of the resulting `.nwb` file, it is integrated with the conversion module (conversion on-click) and allows for visually exploring the data in the end file with [nwb-jupyter-widgets](https://github.com/NeurodataWithoutBorders/nwb-jupyter-widgets).

![](media/gif_gui_buffalo.gif)
