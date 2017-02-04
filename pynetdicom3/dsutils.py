"""
DICOM Dataset utility functions.
"""
import logging

from pydicom.filebase import DicomBytesIO
from pydicom.filereader import read_dataset
from pydicom.filewriter import write_dataset, write_data_element
from pydicom.values import convert_numbers

LOGGER = logging.getLogger('pynetdicom3.dsutils')

def decode(bytestring, is_implicit_vr, is_little_endian):
    """Decode `bytestring` to a pydicom Dataset.

    When sent a DIMSE Message from a peer AE, decode the data and convert
    it to a pydicom Dataset instance.

    Parameters
    ----------
    byestring : io.BytesIO
        The encoded dataset in the DIMSE Message sent from the peer AE.
    is_implicit_vr : bool
        The dataset is encoded as implicit or explicit VR.
    is_little_endian : bool
        The byte ordering of the encoded dataset, little or big endian.

    Returns
    -------
    pydicom.dataset.Dataset
        The decoded dataset.
    """
    ## Logging
    transfer_syntax = "Little Endian" if is_little_endian else "Big Endian"
    if is_implicit_vr:
        transfer_syntax += " Implicit"
    else:
        transfer_syntax += " Explicit"

    LOGGER.debug('pydicom.read_dataset() TransferSyntax="%s"', transfer_syntax)

    ## Decode the dataset
    # Rewind to the start of the stream
    bytestring.seek(0)
    return read_dataset(bytestring, is_implicit_vr, is_little_endian)

def encode(ds, is_implicit_vr, is_little_endian):
    """Encode a pydicom Dataset `ds` to a byte stream.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The dataset to encode
    is_implicit_vr : bool
        The element encoding scheme the dataset will be encoded with.
    is_little_endian : bool
        The byte ordering the dataset will be encoded in.

    Returns
    -------
    bytes or None
        The encoded dataset (if successful), None if the encoding failed.
    """
    # pylint: disable=broad-except
    fp = DicomBytesIO()
    fp.is_implicit_VR = is_implicit_vr
    fp.is_little_endian = is_little_endian
    try:
        write_dataset(fp, ds)
    except Exception as ex:
        LOGGER.error("pydicom.write_dataset() failed:")
        LOGGER.error(ex)
        fp.close()
        return None

    bytestring = fp.parent.getvalue()
    fp.close()

    return bytestring

def encode_element(elem, is_implicit_vr=True, is_little_endian=True):
    """Encode a pydicom DataElement `elem` to a byte stream.

    The default is to encode the element as implicit VR little endian.

    Parameters
    ----------
    elem : pydicom.dataelem.DataElement
        The element to encode
    is_implicit_vr : bool, optional
        The element encoding scheme the element will be encoded with, default
        is True.
    is_little_endian : bool, optional
        The byte ordering the element will be encoded in, default is True.

    Returns
    -------
    bytes
        The encoded element.
    """
    fp = DicomBytesIO()
    fp.is_implicit_VR = is_implicit_vr
    fp.is_little_endian = is_little_endian
    write_data_element(fp, elem)
    bytestring = fp.parent.getvalue()
    fp.close()

    return bytestring

def correct_ambiguous_vr(ds, is_little_endian):
    """Iterate through `dataset` correct ambiguous VR elements.

    Also fixes the element.value as pydicom doesn't always handle decoding
    correctly.

    OB, string of bytes and insensitive to byte ordering
    OW, string of 16-bit words, sensitive to byte ordering
    SS, signed binary int, 16 bits in 2's complement. 2 byte fixed length.
    US, unsigned binary int. 2 byte fixed length.

    Elements with Unsolved Ambiguous VRs
    ------------------------------------
    OB or OW        0014,3050 DarkCurrentCounts (DICONDE)
    OB or OW        0014,3070 AirCounts (DICONDE)
    US or SS        0028,0071 PerimeterValue (Retired)
    US or SS        0028,1100 GrayLookupTableDescriptor (Retired)
    US or SS or OW  0028,1200 GrayLookupTableData (Retired)
    OB or OW        50xx,200C AudioSampleData (Retired)
    OB or OW        50xx,3000 CurveData (Retired)
    OB or OW        60xx,3000 OverlayData
    OB or OW        7Fxx,0010 VariablePixelData (Retired)

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The dataset containing the elements with ambiguous VRs
    is_little_endian : bool
        Whether the dataset is encoded as little or big endian.

    Returns
    -------
    ds : pydicom.dataset.Dataset
        A dataset with (hopefully) unambiguous VRs.

    Raises
    ------
    ValueError
        If the ambiguous VR requires another element within the dataset to
        determine the VR to use, but this element is absent then ValueError will
        be raised.
    """
    for elem in ds:
        # Iterate the correction through any sequences
        if elem.VR == 'SQ':
            for item in elem:
                item = correct_ambiguous_vr(item, is_little_endian)

        if ' or ' in elem.VR:
            # OB or OW: 7fe0,0010 PixelData
            if elem.tag == 0x7fe00010:
                # If BitsAllocated is > 8 then OW, else may be OB or OW
                #   As per PS3.5 Annex A.2. For <= 8, test the size of each
                #   pixel to see if its written in OW or OB
                try:
                    if ds.BitsAllocated > 8:
                        elem.VR = 'OW'
                    else:
                        if len(ds.PixelData) / (ds.Rows * ds.Columns) == 2:
                            elem.VR = 'OW'
                        elif len(ds.PixelData) / (ds.Rows * ds.Columns) == 1:
                            elem.VR = 'OB'
                except AttributeError:
                    raise ValueError("Cannot set VR for PixelData as a "
                                     "required element is missing. Consider "
                                     "using a implicit VR transfer syntax.")

            # US or SS: 0018,9810 ZeroVelocityPixelValue
            # US or SS: 0022,1452 MappedPixelValue
            # US or SS: 0028,0104 SmallestValidPixelValue (Retired)
            # US or SS: 0028,0105 LargestValidPixelValue (Retired)
            # US or SS: 0028,0106 SmallestImagePixelValue
            # US or SS: 0028,0107 LargestImagePixelValue
            # US or SS: 0028,0108 SmallestPixelValueInSeries
            # US or SS: 0028,0109 LargestPixelValueInSeries
            # US or SS: 0028,0110 SmallestImagePixelValueInPlane (Retired)
            # US or SS: 0028,0111 LargestImagePixelValueInPlane (Retired)
            # US or SS: 0028,0120 PixelPaddingValue
            # US or SS: 0028,0121 PixelPaddingRangeLimit
            # US or SS: 0028,1101 RedPaletteColorLookupTableDescriptor
            # US or SS: 0028,1102 BluePaletteColorLookupTableDescriptor
            # US or SS: 0028,1103 GreenPaletteColorLookupTableDescriptor
            # US or SS: 0028,3002 LUTDescriptor
            # US or SS: 0040,9211 RealWorldValueLastValueMapped
            # US or SS: 0040,9216 RealWorldValueFirstValueMapped
            # US or SS: 0060,3004 HistogramFirstBinValue
            # US or SS: 0060,3006 HistogramLastBinValue
            elif elem.tag in [0x00189810, 0x00221452, 0x00280104, 0x00280105,
                              0x00280106, 0x00280107, 0x00280108, 0x00280108,
                              0x00280110, 0x00280111, 0x00280120, 0x00280121,
                              0x00281101, 0x00281102, 0x00281103, 0x00283002,
                              0x00409211, 0x00409216, 0x00603004, 0x00603006]:
                # US if PixelRepresenation value is 0x0000, else SS
                #   For references, see the list at
                #   https://github.com/scaramallion/pynetdicom3/issues/3
                if 'PixelRepresentation' in ds:
                    if ds.PixelRepresentation == 0:
                        elem.VR = 'US'
                        byte_type = 'H'
                    else:
                        elem.VR = 'SS'
                        byte_type = 'h'
                    # Fix for pydicom not handling this correctly
                    elem.value = convert_numbers(elem.value, is_little_endian,
                                                 byte_type)
                else:
                    raise ValueError("Cannot set VR of {} if "
                                     "PixelRepresentation is not in the"
                                     "dataset. Consider a transfer "
                                     "syntax with implicit VR."
                                     .format(elem.keyword))

            # OB or OW: 5400,0110 ChannelMinimumValue
            # OB or OW: 5400,0112 ChannelMaximumValue
            # OB or OW: 5400,100A WaveformPaddingValue
            # OB or OW: 5400,1010 WaveformData
            elif elem.tag in [0x54000100, 0x54000112, 0x5400100A,
                              0x54001010]:
                # OB if WaveformSampleInterpretation value is
                #   SB/UB/MB/AB, else OW. See the list at
                #   https://github.com/scaramallion/pynetdicom3/issues/3
                if 'WaveformBitsAllocated' in ds:
                    if ds.WaveformBitsAllocated > 8:
                        elem.VR = 'OW'
                    else:
                        raise ValueError("Cannot set VR of {} if "
                                         "WaveformBitsAllocated is <= 8. "
                                         "Consider using an implicit VR "
                                         "transfer syntax."
                                         .format(elem.keyword))

                else:
                    raise ValueError("Cannot set VR of {} if "
                                     "WaveformBitsAllocated is "
                                     "not in the dataset. Consider a transfer "
                                     "syntax with implicit VR."
                                     .format(elem.keyword))

            # US or OW: 0028,3006 LUTData
            elif elem.tag in [0x00283006]:
                if 'LUTDescriptor' in ds:
                    # First value in LUT Descriptor is how many values in
                    #   LUTData
                    if ds.LUTDescriptor[0] == 1:
                        elem.VR = 'US'
                        elem.value = convert_numbers(elem.value,
                                                     is_little_endian,
                                                     'H')
                    else:
                        elem.VR = 'OW'
                else:
                    raise ValueError("Cannot set VR of LUTData if "
                                     "LUTDescriptor is not in the dataset. "
                                     "Consider using Implicit VR as the "
                                     "transfer syntax.")
            else:
                raise NotImplementedError("Cannot set VR of {} as the"
                                          " correct method for doing "
                                          "\n   so is not known. Consider "
                                          "using a transfer syntax with "
                                          "implicit VR\n   or "
                                          "setting the VR manually prior to "
                                          "sending."
                                          .format(elem.keyword))

            LOGGER.debug("Setting VR of (%04x, %04x) %s to "
                         "'%s'.", elem.tag.group, elem.tag.elem,
                         elem.name, elem.VR)
    return ds
