import re
import numpy as np
from nexfile import nexfile
from buffalonwb.exceptions import InconsistentInputException, UnsupportedInputException
from hdmf.data_utils import DataChunkIterator


# From Ryan Ly
def add_units(nwbfile, nex_file_name, include_waveforms=False, max_num_channels=1024):
    file_data = nexfile.Reader(useNumpy=True).ReadNexFile(nex_file_name)

    # first half of variables contains spike times, second half contains spike waveforms for each spike time
    num_vars = len(file_data['Variables'])
    start_var = round(num_vars / 2)  # read just the waveform variables

    # sanity checks
    if num_vars % 2 != 0:
        raise InconsistentInputException()

    print('adding ' + str(start_var) + ' units...')

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

    # add these columns to Units table
    nwbfile.add_unit_column('name', 'name')
    nwbfile.add_unit_column('pre_threshold_samples', 'number of samples before threshold')
    nwbfile.add_unit_column('num_samples', 'number of samples for each spike waveform')
    nwbfile.add_unit_column('num_spikes', 'number of spikes')
    nwbfile.add_unit_column('sampling_rate', 'sampling rate')
    nwbfile.add_unit_column('nex_var_version', 'variable version in the NEX5 file')

    # since waveforms are not a 1:1 mapping per unit, use table indexing
    if include_waveforms:
        nwbfile.add_unit_column('waveforms', 'waveforms for each spike', index=True)

    total_spikes_ch = np.zeros((max_num_channels,), dtype=int)
    num_units = num_vars - start_var
    for i in range(4): #num_units):
        var_idx = start_var + i
        var = file_data['Variables'][var_idx]
        var_header = var['Header']
        channel_num = get_channel_num(var_header['Name'])
        total_spikes_ch[channel_num] += var_header['Count']

    channel_end_idxs = np.cumsum(total_spikes_ch, dtype=int)
    channel_start_idxs = np.zeros((max_num_channels,), dtype=int)
    channel_start_idxs[1:] = channel_end_idxs[0:-1]
    total_num_spikes = int(sum(total_spikes_ch))
    added_count = 0

    # support soft clustering
    # each row of the Units table will have a sparse vector 1 x total_num_spikes where each element
    # is the probability that that spike waveform comes from the current unit (the current row)
    nwbfile.add_unit_column('probabilities', 'probability that each spike came from each unit')
                            #data_chunk_iterator_num_vals=total_num_spikes)

    for i in range(4): #num_units):
        var_idx = start_var + i
        var = file_data['Variables'][var_idx]
        var_header = var['Header']
        channel_num = get_channel_num(var_header['Name'])
        electrodes = [channel_num]
        num_spikes = var_header['Count']

        # TODO wrap in H5DataIO???? specify fillvalue = np.nan??
        print(channel_start_idxs[channel_num], channel_end_idxs[channel_num], added_count, added_count + num_spikes)
        probs_iter = DataChunkIterator(
            data=get_unit_probs_per_spike(
                channel_start_idx=channel_start_idxs[channel_num],
                channel_end_idx=channel_end_idxs[channel_num],
                unit_start_idx=added_count,
                unit_end_idx=added_count + num_spikes,
                total_wfs=total_num_spikes,
                chunk_length=1
            ),
            maxshape=(total_num_spikes * num_units,),
            buffer_size=100
        )
        added_count += num_spikes

        kwargs = dict()
        if include_waveforms:
            kwargs.update(waveforms=var['WaveformValues'])

        nwbfile.add_unit(electrodes=electrodes,
                         name=var_header['Name'],
                         spike_times=var['Timestamps'],
                         pre_threshold_samples=var_header['PreThrTime'],
                         num_samples=var_header['NPointsWave'],
                         num_spikes=var_header['Count'],
                         sampling_rate=var_header['SamplingRate'],
                         nex_var_version=var_header['Version'],
                         probabilities=probs_iter,
                         **kwargs)


def get_channel_num(unit_name):
    # neuralynx -> plexon offline sorter unit variable names have the format
    # CSC[int]-[char] -- the int is the channel number (starts at 1)
    digit_match = re.search(r'\d+', unit_name)
    if not digit_match:
        raise UnsupportedInputException('Cannot parse name of unit: %s' % unit_name)
    return int(digit_match.group())


def get_unit_probs_per_spike(channel_start_idx, channel_end_idx, unit_start_idx, unit_end_idx, total_wfs,
                             chunk_length=100):
    """
    Iterator that yields the probability that a given unit generated each of the N spike waveforms,
    where N is the total number of spikes across all units. The iterator returns chunks of variable size,
    of either value None, 0, or 1 (until soft clustering is implemented).
    It is assumed that each unit
    generates waveforms only on a single channel and each spike waveform can have non-zero probabilities
    only on the units recorded on the corresponding channel. If a spike waveform was recorded on a
    different channel than the given unit, this iterator yields None. If a spike waveform was recorded
    on the same channel as the given unit but the probability that the unit is associated with that
    waveform, this iterator yields 0.0. Using the HDF5 backend to NWB, None values (which will make up
    the majority of the values yielded by this iterator) are not written to disk, thus saving
    significant space. ASSUMES units are grouped by channel.

    channel_start_idx
    channel_end_idx - exclusive
    unit_start_idx
    unit_end_idx - exclusive
    """

    # check inputs
    if channel_start_idx > channel_end_idx:
        raise InconsistentInputException('Channel start index must be <= channel end index')
    if unit_start_idx > unit_end_idx:
        raise InconsistentInputException('Unit start index must be <= unit end index')
    if channel_start_idx > unit_start_idx:
        raise InconsistentInputException('Channel start index must be <= unit start index')
    if unit_end_idx > channel_end_idx:
        raise InconsistentInputException('Unit end index must be <= channel end index')
    if channel_end_idx > total_wfs:
        raise InconsistentInputException('Channel end index must be <= total number of waveforms')
    if channel_start_idx < 0:
        raise InconsistentInputException('Channel start index must be >= 0')
    if chunk_length <= 0:
        raise InconsistentInputException('Chunk length must be > 0')
    if total_wfs == 0:
        yield None

    # easy way (could compute chunks on the fly instead of allocating the whole array)
    full_array = np.ones((total_wfs, 1)) * np.nan  # nan will be yielded as None
    full_array[channel_start_idx:channel_end_idx] = 0
    full_array[unit_start_idx:unit_end_idx] = 1

    count = 0
    while count < total_wfs:
        if count + chunk_length <= total_wfs:
            chunk_end = count + chunk_length
        else:
            chunk_end = total_wfs
        chunk = full_array[count:chunk_end]

        if np.all(np.isnan(chunk)):
            yield None
        else:
            yield chunk
        count += chunk_length
