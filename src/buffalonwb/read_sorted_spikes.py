import sys
from pprint import pprint
from nexfile import nexfile


class InconsistentInputException(Exception):
    pass


class UnsupportedInputException(Exception):
    pass


def add_units():
    reader = nexfile.Reader(useNumpy=True)
    file_data = reader.ReadNexFile(sys.argv[1])
    file_header = file_data['FileHeader']  # dict of .nex file info
    writer_software = file_data['MetaData']['file']['writerSoftware']  # dict of name, version

    num_vars = len(file_data['Variables'])
    start_var = round(num_vars / 2)

    # sanity checks
    if num_vars % 2 != 0:
        raise InconsistentInputException()

    for i in range(start_var, num_vars):
        if file_data['Variables'][i]['Header']['Type'] != 3:  # 3 = waveform
            raise UnsupportedInputException()
        if file_data['Variables'][i]['Header']['Units'] != 'mV':
            raise UnsupportedInputException()
        if file_data['Variables'][160]['Header']['TsDataType'] != 1:  # 1 = 64-bit integer
            raise UnsupportedInputException()
        if file_data['Variables'][160]['Header']['ADtoMV'] == 0:
            raise UnsupportedInputException()
        if (file_data['Variables'][i - start_var]['Timestamps'] != file_data['Variables'][i]['Timestamps']).any():
            raise InconsistentInputException()
        if file_data['Variables'][i]['Timestamps'].shape != (file_data['Variables'][i]['Header']['Count'], ):
            raise InconsistentInputException()
        if file_data['Variables'][i]['WaveformValues'].shape != \
            (file_data['Variables'][i]['Header']['Count'], file_data['Variables'][i]['Header']['NPointsWave']):
            raise InconsistentInputException()
        if file_data['Variables'][i]['WaveformValues'].shape != \
            (file_data['Variables'][i]['Header']['Count'], file_data['Variables'][i]['Header']['NPointsWave']):
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
    #             if 1, waveform and continuous values are stored as 32-bit floating point values in units specified in Units field
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
    nwbfile.add_unit_column('name', 'name')
    nwbfile.add_unit_column('pre_threshold_samples', 'number of samples before threshold')
    nwbfile.add_unit_column('num_samples', 'number of samples for each spike waveform')
    nwbfile.add_unit_column('num_spikes', 'number of spikes')
    nwbfile.add_unit_column('sampling_rate', 'sampling rate')
    nwbfile.add_unit_column('nex_var_version', 'variable version in the NEX5 file')

    # since waveforms are not a 1:1 mapping per unit, use table indexing
    nwbfile.add_unit_column('waveforms', 'waveforms for each spike', index=True)

    for i in range(start_var, num_vars):
        nwbfile.add_unit(electrodes=1,  # TODO
                         name=file_data['Variables'][i]['Header']['Name']
                         spike_times=file_data['Variables'][i]['Timestamps'],
                         pre_threshold_samples=file_data['Variables'][i]['PreThrTime']
                         num_samples=file_data['Variables'][i]['Header']['NPointsWave'],
                         num_spikes=file_data['Variables'][i]['Header']['Count']
                         sampling_rate=file_data['Variables'][i]['Header']['SamplingRate'],
                         nex_var_version=file_data['Variables'][i]['Header']['Version']
                         waveforms=file_data['Variables'][i]['WaveformValues'])


def main():
    # USER NEEDS TO INPUT:

    # create the NWBFile instance
    session_description = 'ADDME'
    id = 'ADDME'
    session_start_time = 'ADDME'
    timezone = pytz.timezone('US/Pacific')
    experimenter = 'Yoni Browning'
    lab = 'Buffalo Lab'
    institution = 'University of Washington'
    experiment_description = 'ADDME'
    session_id = 'ADDME'
    data_collection = 'ADDME'

    session_start_time = timezone.localize(session_start_time)
    nwbfile = NWBFile(session_description=session_description,
                      identifier=id,
                      session_start_time=session_start_time,
                      experimenter=experimenter,
                      lab=lab,
                      institution=institution,
                      experiment_description=experiment_description,
                      session_id=session_id,
                      data_collection=data_collection)

    device_name = 'Neuralynx ADDME'
    device = nwbfile.create_device(name=device_name)

    # TODO create electrode groups
    # TODO create electrodes

    add_units(nwbfile)

    # write NWB file to disk
    out_file = './output/nwb_test.nwb'
    with NWBHDF5IO(out_file, 'w') as io:
        print('Writing to file: ' + out_file)
        io.write(nwbfile)

if __name__ == '__main__':
    main()
