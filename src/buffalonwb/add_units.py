from nexfile import nexfile
from buffalonwb.exceptions import InconsistentInputException, UnsupportedInputException
import numpy as np


# From Ryan Ly
def add_units(nwbfile, nex_file_name, include_waveforms=False):

    file_data = nexfile.Reader(useNumpy=True).ReadNexFile(nex_file_name)
    t0 = file_data["FileHeader"]["Beg"]

    # first half of variables contains spike times, second half contains spike waveforms for each spike time
    num_vars = len(file_data['Variables'])
    print('adding ' + str(round(num_vars / 2)) + ' units')
    start_var = round(num_vars / 2)  # read just the waveform variables

    # sanity checks
    if num_vars % 2 != 0:
        raise InconsistentInputException()

    for i in range(start_var, num_vars):
        var = file_data['Variables'][i]
        var_header = var['Header']
        var_ts_only = file_data['Variables'][i - start_var]
        if var_header['Type'] != 3:  # 3 = waveform
            raise UnsupportedInputException()
        if var_header['Units'] != 'mV':
            raise UnsupportedInputException()
        if var_header['TsDataType'] != 1:  # 1 = 64-bit integer
            raise UnsupportedInputException()
        if var_header['ADtoMV'] == 0:
            raise UnsupportedInputException()
        if (var_ts_only['Timestamps'] != var['Timestamps']).any():
            raise InconsistentInputException()
        if var['Timestamps'].shape != (var_header['Count'], ):
            raise InconsistentInputException()
        if var['WaveformValues'].shape != (var_header['Count'], var_header['NPointsWave']):
            raise InconsistentInputException()

    # var["Header"]["Type"] -- 3 - waveform
    # var["Header"]["Name"] -- variable name
    # var["Header"]["Version"] -- variable version in file
    # var["Header"]["Count"] -- number of waveforms
    # var["Header"]["TsDataType"] --
    #             if 0, timestamps are stored as 32-bit integers;
    #             if 1, timestamps are stored as 64-bit integers;
    #             supported by NeuroExplorer version 5.100 or greater
    # var["Header"]["ContDataType"] --
    #             if 0, waveform and continuous values are stored as 16-bit integers;
    #             if 1, waveform and continuous values are stored as 32-bit floating point values in units specified in
    #             Units field
    # var["Header"]["SamplingRate"] -- waveform sampling frequency in Hertz
    # var["Header"]["ADtoMV"] --
    #             coefficient to convert from A/D values stored in file to units.
    #             A/D values in fileData are already scaled to units.
    #             see formula below MVOffset below;
    # var["Header"]["MVOffset"] --
    #             this offset is used to convert A/D values stored in file to units:
    #             value_in_units = raw * ADtoUnitsCoefficient + UnitsOffset;
    #             A/D values in fileData are already scaled to units.
    # var["Header"]["NPointsWave"] -- number of data points in each waveform
    # var["Header"]["PreThrTime"] -- pre-threshold time in seconds
    #             if waveform timestamp in seconds is t,
    #             then the timestamp of the first point of waveform is t - PrethresholdTimeInSeconds

    # add these columns to unit table
    nwbfile.add_unit_column('label', 'NEX label of cluster')
    nwbfile.add_unit_column('pre_threshold_samples', 'number of samples before threshold')
    nwbfile.add_unit_column('num_spikes', 'number of spikes')
    nwbfile.add_unit_column('sampling_rate', 'sampling rate')
    nwbfile.add_unit_column('nex_var_version', 'variable version in the NEX5 file')

    # since waveforms are not a 1:1 mapping per unit, use table indexing
    if include_waveforms:
        nwbfile.add_unit_column('waveforms', 'waveforms for each spike', index=True)
        nwbfile.add_unit_column('num_samples', 'number of samples for each spike waveform')

    for i in range(start_var, num_vars):
        var = file_data['Variables'][i]
        var_header = var['Header']
        kwargs = dict()
        if include_waveforms:
            kwargs.update(waveforms=var['WaveformValues'])
            kwargs.update(num_samples=var_header['Count'])

        nwbfile.add_unit(electrodes=(int(var_header['Name'][3:-2]) - 1,),
                         label=var_header['Name'],
                         spike_times=np.array(var['Timestamps']) - t0,
                         pre_threshold_samples=var_header['PreThrTime'],
                         num_spikes= len(var['Timestamps']),
                         sampling_rate=var_header['SamplingRate'],
                         nex_var_version=var_header['Version'],
                         **kwargs)
