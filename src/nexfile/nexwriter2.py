import struct
import json

from .nexfile import NexWriter, NexFileVarType


class NexWriter2(NexWriter):
    """
    Overwrite the original NexWriter class to handle case where data is stored as the original int16 values and a
    conversion factor is given. If the data are instead provided as floats in units of millivolts after scaling with the
    conversion factor, then the scaling factor used in the NexWriter is computed (see _CalculateScaling in nexfile.py)
    inaccurately, at least as can be observed in Offline Sorter v4.4.2.
    """

    def __init__(self, timestampFrequency, useNumpy=False):
        super(NexWriter2, self).__init__(timestampFrequency, useNumpy)

    def WriteNex5File(self, filePath, saveContValuesAsFloats=0, conversion=None):
        """
        Writes file data as .nex5 file. Overwrites the original function in nexfile.py to allow specification of
        a conversion factor.
        :param filePath: full path of file
        :param saveContValuesAsFloats: if zero, continuous values are saved as 16-bit integers; if 1, saved as floats
        :param conversion: if None, then scaling factor is automatically computed. otherwise, it is used as the scaling
        factor
        :return:
        """
        self.theFile = open(filePath, 'wb')
        self.fileData['FileHeader']['MagicNumber'] = 894977358
        self.fileData['FileHeader']['NexFileVersion'] = 501
        nvars = len(self.fileData['Variables'])
        self.fileData['FileHeader']['NumVars'] = nvars

        maxTs = self._MaximumTimestamp()
        tsAs64 = 0
        if round(maxTs * self.tsFreq) > pow(2, 31):
            tsAs64 = 1
            self.fileData['FileHeader']['NexFileVersion'] = 502

        for v in self.fileData['Variables']:
            v['Header']['TsDataType'] = tsAs64
            v['Header']['Version'] = 500
            v['Header']['ContDataType'] = saveContValuesAsFloats
            if v['Header']['Type'] == NexFileVarType.MARKER:
                self._CalcMarkerLength(v)
                if v['AllNumbers']:
                    v['Header']['MarkerDataType'] = 1
                else:
                    v['Header']['MarkerDataType'] = 0
            # MAIN CHANGE - only use this code if passing in int16 and a conversion factor
            assert(saveContValuesAsFloats == 0)
            assert(conversion is not None)
            v['Header']['ADtoMV'] = conversion

        self.fileData['FileHeader']['BegTicks'] = int(round(self.fileData['FileHeader']['Beg'] * self.tsFreq))
        self.fileData['FileHeader']['EndTicks'] = int(round(maxTs * self.tsFreq))

        dataOffset = 356 + nvars * 244
        for v in self.fileData['Variables']:
            v['Header']['Count'] = self._VarCount(v)
            v['Header']['DataOffset'] = dataOffset
            dataOffset += self._VarNumDataBytes(v)

        fileHeaderFormat = '<i <i 256s <d <q <i <Q <q 56s'.split()
        for i in range(len(self.nex5fileHeaderKeysToWrite)):
            self._WriteField(fileHeaderFormat[i], self.fileData['FileHeader'][self.nex5fileHeaderKeysToWrite[i]])

        varHeaderFormat = '<i <i 64s <Q <Q <i <i <d 32s <d <d <Q <d <i <i <i <i 60s'.split()
        for v in self.fileData['Variables']:
            for i in range(len(self.nex5VarHeaderKeys)):
                self._WriteField(varHeaderFormat[i], v['Header'][self.nex5VarHeaderKeys[i]])

        for v in self.fileData['Variables']:
            self._VarWriteData(v)

        metaData = {"file": {}, 'variables': []}
        metaData["file"]["writerSoftware"] = {}
        metaData["file"]["writerSoftware"]["name"] = 'nexfile.py'
        metaData["file"]["writerSoftware"]["version"] = 'May-06-2017'
        for v in self.fileData['Variables']:
            varMeta = {'name': v['Header']['Name']}
            if v['Header']['Type'] == NexFileVarType.NEURON or v['Header']['Type'] == NexFileVarType.WAVEFORM:
                varMeta['unitNumber'] = v['Header']['Unit']
                varMeta['probe'] = {}
                varMeta['probe']['wireNumber'] = v['Header']['Wire']
                varMeta['probe']['position'] = {}
                varMeta['probe']['position']['x'] = v['Header']['XPos']
                varMeta['probe']['position']['y'] = v['Header']['YPos']
            metaData['variables'].append(varMeta)

        metaString = json.dumps(metaData).encode('utf-8')
        pos = self.theFile.tell()
        self.theFile.write(metaString)
        metaPosInHeader = 284
        self.theFile.seek(metaPosInHeader, 0)
        self.theFile.write(struct.pack('<Q', pos))

        self.theFile.close()

    def _VarWriteContinuousValuesNumpy(self, var):
        """
        Writes continuous data to file. Only use this code if passing in int16 and a conversion factor. Overwrites the
        original function in nexfile.py.
        """
        import numpy as np
        assert(self._BytesInContValue(var) == 2)
        assert(isinstance(var['ContinuousValues'], np.ndarray))
        assert(var['ContinuousValues'].dtype is np.dtype('int16'))

        var['ContinuousValues'].tofile(self.theFile)
