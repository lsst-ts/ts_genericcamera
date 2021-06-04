# This file is part of ts_GenericCamera.
#
# Developed for the Vera Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import enum
import ctypes
from ctypes.util import find_library
import struct
import numpy as np

from .genericcamera import GenericCamera
from ..exposure import Exposure


class AndorCamera(GenericCamera):
    def __init__(self, log=None):
        super().__init__(log)
        self.lib = ATLibrary()
        self.lib.initialiseLibrary()
        self.isLiveExposure = False

    @staticmethod
    def name():
        """Set camera name."""
        return "Andor"

    def initialise(self, config):
        """Initialise the camera with the specified configuration file.

        Parameters
        ----------
        config : str
            The name of the configuration file to load."""
        self.id = 0
        self.accumulateCount = 1
        self.binValue = 1
        self.normalImageType = "Mono16"
        self.currentImageTYpe = self.normalImageType
        self.dev = self.lib.openZyla(self.id)

    def getMakeAndModel(self):
        """Get the make and model of the camera.

        Returns
        -------
        str
            The make and model of the camera."""
        return self.dev.getCameraModel() + " " + self.dev.getCameraName()

    def setROI(self, top, left, width, height):
        """Sets the region of interest.

        Parameters
        ----------
        top : int
            The top most pixel of the region.
        left : int
            The left most pixel of the region.
        width : int
            The width of the region in pixels.
        height : int
            The height of the region in pixels."""
        self.dev.setAOITop(top)
        self.dev.setAOILeft(left)
        self.dev.setAOIWidth(width)
        self.dev.setAOIHeight(height)

    def getROI(self):
        """Gets the region of interest.

        Returns
        -------
        int
            The top most pixel of the region.
        int
            The left most pixel of the region.
        int
            The width of the region in pixels.
        int
            The height of the region in pixels."""
        top = self.dev.getAOITop()
        left = self.dev.getAOILeft()
        width = self.dev.getAOIWidth()
        height = self.dev.getAOIHeight()
        return top, left, width, height

    def setFullFrame(self):
        """Sets the region of interest to the whole sensor."""
        result, width = self.dev.at.getIntMax(self.dev.handle, Features.AOIWidth)
        result, height = self.dev.at.getIntMax(self.dev.handle, Features.AOIHeight)
        self.setROI(0, 0, width, height)

    def setExposureTime(self, duration):
        """Sets the exposure time.

        Parameters
        ----------
        duration : float
            The exposure time in seconds."""
        self.dev.setExposureTime(duration)

    def configureForLiveView(self):
        """Configure the camera for live view.

        This should change the image format to 8bits per pixel so
        the image can be encoded to JPEG."""
        self.isLiveExposure = True

    def configureForExposure(self):
        """Configure the camera for a standard exposure."""
        self.isLiveExposure = False

    async def takeExposure(self):
        """Take an exposure with the currently configured settings.

        The exposure should be the raw image data from the camera which
        most likely means a buffer created by
        ctypes.ctypes.create_string_buffer()

        The Exposure class handles converting the image to the correct
        format. If live view, the image data is converted into a JPEG
        to be sent over a TCP socket. If a standard exposure then the
        image data is converted into a FITS to be saved onto the local
        machine.

        Returns
        -------
        Exposure
            The exposure captured by the camera."""
        self.dev.flush()
        buffer = self.dev.queueBuffer()
        self.dev.cmdAcquisitionStart()
        bytesReceived = 0
        while bytesReceived == 0:
            try:
                bytesReceived = self.dev.waitBuffer(buffer, 0)
                await asyncio.sleep(0.02)
            except ATError as e:
                if e.result != Results.TimedOut:
                    raise e
        top = self.dev.getAOITop()
        left = self.dev.getAOILeft()
        width = self.dev.getAOIWidth()
        height = self.dev.getAOIHeight()
        exposure = self.dev.getExposureTime()
        temperature = self.dev.getSensorTemperature()
        if self.isLiveExposure:
            ints = struct.unpack("H" * (width * height), buffer)
            pixels16 = np.asarray(ints)
            pixels8 = (pixels16 / 256).astype(np.uint8)
            buffer = pixels8
        tags = {
            "TOP": top,
            "LEFT": left,
            "WIDTH": width,
            "HEIGHT": height,
            "EXPOSURE": exposure,
            "TEMPERATURE": temperature,
        }
        return Exposure(buffer, width, height, tags)


class Results(enum.Enum):
    Success = 0
    NotInitialised = 1
    NotImplemented = 2
    ReadOnly = 3
    NotReadable = 4
    NotWritable = 5
    OutOfRange = 6
    IndexNotAvailable = 7
    IndexNotImplemented = 8
    ExceededMaxStringLength = 9
    Connection = 10
    NoData = 11
    InvalidHandle = 12
    TimedOut = 13
    BufferFull = 14
    InvalidSize = 15
    InvalidAlignment = 16
    Comm = 17
    StringNotAvailable = 18
    StringNotImplemented = 19
    NullFeature = 20
    NullHandle = 21
    NullImplementedVar = 22
    NullReadableVar = 23
    NullReadonlyVar = 24
    NullWritable = 25
    NullMinValue = 26
    NullMaxValue = 27
    NullValue = 28
    NullString = 29
    NullCountVar = 30
    NullIsAvailableVar = 31
    NullMaxStringLength = 32
    NullEvCallback = 33
    NullQueuePointer = 34
    NullWaitPointer = 35
    NullPointerSize = 36
    NoMemory = 37
    DeviceInUse = 38
    DeviceNotFound = 39
    HardwareOverflow = 100


class Features(enum.IntEnum):
    AccumulateCount = 100  # Int
    AcquisitionStart = 1  # Command
    AcquisitionStop = 2  # Command
    AlternatingReadoutDirection = 203  # Bool
    AOIBinning = 304  # Enumerated (1x1, 2x2, 3x3, 4x4, 8x8)
    AOIHBin = 105  # Int
    AOIHeight = 106  # Int
    AOILayout = 307  # Enumerated (Image, Multitrack)
    AOILeft = 108  # Int
    AOIStride = 109  # Int
    AOITop = 110  # Int
    AOIVBin = 111  # Int
    AOIWidth = 112  # Int
    AuxiliaryOutSource = 313  # Enumerated (FireRow1, FireRowN, FireAll, FireAny)
    # Enumerated (ExternalShutterControl, FrameClock, RowClock, ExposedRowClow)
    AuxOutSourceTwo = 314
    Baseline = 115  # Int
    BitDepth = 316  # Enumerated (11Bit or 12Bit, 16Bit)
    BufferOverflowEvent = 117  # Int
    BytesPerPixel = 418  # Float
    CameraAcquiring = 219  # Bool
    CameraDump = 20  # Command
    CameraModel = 521  # String
    CameraName = 522  # String
    CameraPresent = 223  # Bool
    ControllerID = 524  # String
    FrameCount = 125  # Int
    CycleMode = 326  # Enumerated (Fixed, Continuous)
    DeviceCount = 127  # Int
    ElectronicShutteringMode = 328  # Enumerated (Rolling, Global)
    EventEnable = 229  # Bool
    EventsMissedEvent = 130  # Int
    # Enumerated (ExposureEndEvent, ExposureStartEvent, RowNExposureEndEvent,
    # RowNExposureStartEvent, EventsMissedEvent, BufferOverflowEvent)
    EventSelector = 331
    ExposedPixelHeight = 132  # Int
    ExposureTime = 433  # Float
    ExposureEndEvent = 134  # Int
    ExposureStartEvent = 135  # Int
    ExternalTriggerDelay = 436  # Float
    FanSpeed = 337  # Enumerated (Off, Low, On)
    FastAOIFrameRateEnabled = 238  # Bool
    FirmwareVersion = 539  # String
    FrameRate = 440  # Float
    FullAOIControl = 241  # Bool
    ImageSizeBytes = 142  # Int
    InterfaceType = 543  # String
    IOInvert = 244  # Bool
    IOSelector = 345  # Enumerated (Fire1, FireN, AuxOut1, Arm, ExternalTrigger)
    LineScanSpeed = 446  # Float
    LUTIndex = 147  # Int
    LUTValue = 148  # Int
    MaxInterfaceTransferRate = 449  # Float
    MetadataEnable = 250  # Bool
    MetadataTimestamp = 251  # Bool
    MetadataFrame = 252  # Bool
    MultitrackBinned = 253  # Bool
    MultitrackCount = 154  # Int
    MultitrackEnd = 155  # Int
    MultitrackSelector = 156  # Int
    MultitrackStart = 157  # Int
    Overlap = 258  # Bool
    PixelEncoding = 359  # Enumerated (Mono12, Mono12Packed, Mono16, Mono32)
    PixelHeight = 460  # Float
    PixelReadoutRate = 361  # Enumerated (280MHz, 200MHz, 100MHz)
    PixelWidth = 462  # Float
    # Enumerated (Gain1 (11bit),Gain2 (11 bit), Gain3 (11bit), Gain4 (11bit),
    # Gain1 Gain3 (16bit), Gain1 Gain4 (16bit), Gain2 Gain3 (16bit), Gain2,
    # Gain4 (16bit))
    PreAmpGainControl = 363
    ReadoutTime = 464  # Float
    RollingShutterGlobalClear = 265  # Bool
    RowNExposureEndEvent = 166  # Int
    RowNExposureStartEvent = 167  # Int
    RowReadTime = 468  # Float
    ScanSpeedControlEnable = 269  # Bool
    SensorCooling = 270  # Bool
    SensorHeight = 171  # Int
    # Enumerated (Bottom Up Sequential, Bottom Up Simultaneous, Centre Out
    # Simultaneous, Outside In Simultaneous, Top Down Sequential, Top Down
    # Simultaneous)
    SensorReadoutMode = 372
    SensorTemperature = 473  # Float
    SensorWidth = 174  # Int
    SerialNumber = 575  # String
    ShutterOutputMode = 376  # Enumerated (Open, Closed)
    # Enumerated (11-bit (high well capacity) or 12-bit (high well capacity),
    # 11-bit (low noise) or 12-bit (low noise), 16-bit (low noise & high well
    # capacity))
    SimplePreAmpGainControl = 377
    ShutterTransferTime = 478  # Float
    SoftwareTrigger = 79  # Command
    StaticBlemishCorrection = 280  # Bool
    SpuriousNoiseFilter = 281  # Bool
    TargetSensorTemperature = 482  # Float
    TemperatureControl = 383  # Enumerated
    # Enumerated (Cooler Off, Stabilised, Cooling, Drift, Not Stabilised,
    # Fault)
    TemperatureStatus = 384
    TimestampClock = 185  # Int
    TimestampClockFrequency = 186  # Int
    TimestampClockReset = 87  # Command
    # Enumerated (Interal, Software, External, External Start,
    # External Exposure)
    TriggerMode = 388
    VerticallyCentreAOI = 289  # Bool


class AT:
    def __init__(self):
        lib = ctypes.CDLL(find_library("atcore"))

        # int AT_EXP_CONV AT_InitialiseLibrary();
        lib.AT_InitialiseLibrary.restype = ctypes.c_int

        # int AT_EXP_CONV AT_FinaliseLibrary();
        lib.AT_FinaliseLibrary.restype = ctypes.c_int

        # int AT_EXP_CONV AT_Open(int CameraIndex, AT_H *Hndl);
        lib.AT_Open.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        lib.AT_Open.restype = ctypes.c_int

        # int AT_EXP_CONV AT_Close(AT_H Hndl);
        lib.AT_Close.argtypes = [ctypes.c_int]
        lib.AT_Close.restype = ctypes.c_int

        # typedef int (AT_EXP_CONV *FeatureCallback)(AT_H Hndl, const AT_WC*
        # Feature, void* Context);
        # int AT_EXP_CONV AT_RegisterFeatureCallback(AT_H Hndl, const AT_WC*
        # Feature, FeatureCallback EvCallback, void* Context);
        # int AT_EXP_CONV AT_UnregisterFeatureCallback(AT_H Hndl, const AT_WC*
        # Feature, FeatureCallback EvCallback, void* Context);

        # int AT_EXP_CONV AT_IsImplemented(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* Implemented);
        lib.AT_IsImplemented.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_bool),
        ]
        lib.AT_IsImplemented.restype = ctypes.c_int

        # int AT_EXP_CONV AT_IsReadable(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* Readable);
        lib.AT_IsReadable.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_bool),
        ]
        lib.AT_IsReadOnly.restype = ctypes.c_int

        # int AT_EXP_CONV AT_IsWritable(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* Writable);
        lib.AT_IsWritable.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_bool),
        ]
        lib.AT_IsWritable.restype = ctypes.c_int

        # int AT_EXP_CONV AT_IsReadOnly(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* ReadOnly);
        lib.AT_IsReadOnly.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_bool),
        ]
        lib.AT_IsReadOnly.restype = ctypes.c_int

        # int AT_EXP_CONV AT_SetInt(AT_H Hndl, const AT_WC* Feature,
        # AT_64 Value);
        lib.AT_SetInt.argtypes = [ctypes.c_int, ctypes.c_wchar_p, ctypes.c_longlong]
        lib.AT_SetInt.restype = ctypes.c_int

        # int AT_EXP_CONV AT_GetInt(AT_H Hndl, const AT_WC* Feature,
        # AT_64* Value);
        lib.AT_GetInt.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_longlong),
        ]
        lib.AT_GetInt.restype = ctypes.c_int

        # int AT_EXP_CONV AT_GetIntMax(AT_H Hndl, const AT_WC* Feature,
        # AT_64* MaxValue);
        lib.AT_GetIntMax.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_longlong),
        ]
        lib.AT_GetIntMax.restype = ctypes.c_int

        # int AT_EXP_CONV AT_GetIntMin(AT_H Hndl, const AT_WC* Feature,
        # AT_64* MinValue);
        lib.AT_GetIntMin.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_longlong),
        ]
        lib.AT_GetIntMin.restype = ctypes.c_int

        # int AT_EXP_CONV AT_SetFloat(AT_H Hndl, const AT_WC* Feature,
        # double Value);
        lib.AT_SetFloat.argtypes = [ctypes.c_int, ctypes.c_wchar_p, ctypes.c_double]
        lib.AT_SetFloat.restype = ctypes.c_int

        # int AT_EXP_CONV AT_GetFloat(AT_H Hndl, const AT_WC* Feature,
        # double* Value);
        lib.AT_GetFloat.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_double),
        ]
        lib.AT_GetFloat.restype = ctypes.c_int

        # int AT_EXP_CONV AT_GetFloatMax(AT_H Hndl, const AT_WC* Feature,
        # double* MaxValue);
        lib.AT_GetFloatMax.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_double),
        ]
        lib.AT_GetFloatMax.restype = ctypes.c_int

        # int AT_EXP_CONV AT_GetFloatMin(AT_H Hndl, const AT_WC* Feature, d
        # ouble* MinValue);
        lib.AT_GetFloatMin.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_double),
        ]
        lib.AT_GetFloatMin.restype = ctypes.c_int

        # int AT_EXP_CONV AT_SetBool(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL Value);
        lib.AT_SetBool.argtypes = [ctypes.c_int, ctypes.c_wchar_p, ctypes.c_bool]
        lib.AT_SetBool.restype = ctypes.c_int

        # int AT_EXP_CONV AT_GetBool(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* Value);
        lib.AT_GetBool.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_bool),
        ]
        lib.AT_GetBool.restype = ctypes.c_int

        # int AT_EXP_CONV AT_SetEnumerated(AT_H Hndl, const AT_WC* Feature,
        # int Value);
        lib.AT_SetEnumerated.argtypes = [ctypes.c_int, ctypes.c_wchar_p, ctypes.c_int]
        lib.AT_SetEnumerated.restype = ctypes.c_int

        # int AT_EXP_CONV AT_SetEnumeratedString(AT_H Hndl, const AT_WC*
        # Feature, const AT_WC* String);
        lib.AT_SetEnumeratedString.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
        ]
        lib.AT_SetEnumeratedString.restype = ctypes.c_int

        # int AT_EXP_CONV AT_GetEnumerated(AT_H Hndl, const AT_WC* Feature,
        # int* Value);
        lib.AT_GetEnumerated.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.AT_GetEnumerated.restype = ctypes.c_int

        # int AT_EXP_CONV AT_GetEnumeratedCount(AT_H Hndl,const  AT_WC*
        # Feature, int* Count);
        lib.AT_GetEnumCount.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.AT_GetEnumCount.restype = ctypes.c_int

        # int AT_EXP_CONV AT_IsEnumeratedIndexAvailable(AT_H Hndl, const
        # AT_WC* Feature, int Index, AT_BOOL* Available);
        lib.AT_IsEnumeratedIndexAvailable.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_bool),
        ]
        lib.AT_IsEnumIndexAvailable.restype = ctypes.c_int

        # int AT_EXP_CONV AT_IsEnumeratedIndexImplemented(AT_H Hndl,
        # const AT_WC* Feature, int Index, AT_BOOL* Implemented);
        lib.AT_IsEnumeratedIndexImplemented.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_bool),
        ]
        lib.AT_IsEnumeratedIndexImplemented.restype = ctypes.c_int

        # int AT_EXP_CONV AT_GetEnumeratedString(AT_H Hndl, const AT_WC*
        # Feature, int Index, AT_WC* String, int StringLength);
        lib.AT_GetEnumeratedString.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.c_int,
        ]
        lib.AT_GetEnumeratedString.restype = ctypes.c_int

        # int AT_EXP_CONV AT_SetEnumIndex(AT_H Hndl, const AT_WC* Feature,
        # int Value);
        lib.AT_SetEnumIndex.argtypes = [ctypes.c_int, ctypes.c_wchar_p, ctypes.c_int]
        lib.AT_SetEnumIndex.restype = ctypes.c_int

        # int AT_EXP_CONV AT_SetEnumString(AT_H Hndl, const AT_WC* Feature,
        # const AT_WC* String);
        lib.AT_SetEnumString.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
        ]
        lib.AT_SetEnumString.restype = ctypes.c_int

        # int AT_EXP_CONV AT_GetEnumIndex(AT_H Hndl, const AT_WC* Feature,
        # int* Value);
        lib.AT_GetEnumIndex.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.AT_GetEnumIndex.restype = ctypes.c_int

        # int AT_EXP_CONV AT_GetEnumCount(AT_H Hndl,const  AT_WC* Feature,
        # int* Count);
        lib.AT_GetEnumCount.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.AT_GetEnumCount.restype = ctypes.c_int

        # int AT_EXP_CONV AT_IsEnumIndexAvailable(AT_H Hndl, const AT_WC*
        # Feature, int Index, AT_BOOL* Available);
        lib.AT_IsEnumIndexAvailable.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_bool),
        ]
        lib.AT_IsEnumIndexAvailable.restype = ctypes.c_int

        # int AT_EXP_CONV AT_IsEnumIndexImplemented(AT_H Hndl, const AT_WC*
        # Feature, int Index, AT_BOOL* Implemented);
        lib.AT_IsEnumIndexImplemented.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_bool),
        ]
        lib.AT_IsEnumIndexImplemented.restype = ctypes.c_int

        # int AT_EXP_CONV AT_GetEnumStringByIndex(AT_H Hndl, const AT_WC*
        # Feature, int Index, AT_WC* String, int StringLength);
        lib.AT_GetEnumStringByIndex.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.c_int,
        ]
        lib.AT_GetEnumStringByIndex.restype = ctypes.c_int

        # int AT_EXP_CONV AT_Command(AT_H Hndl, const AT_WC* Feature);
        lib.AT_Command.argtypes = [ctypes.c_int, ctypes.c_wchar_p]
        lib.AT_Command.restype = ctypes.c_int

        # int AT_EXP_CONV AT_SetString(AT_H Hndl, const AT_WC* Feature,
        # const AT_WC* String);
        lib.AT_SetString.argtypes = [ctypes.c_int, ctypes.c_wchar_p, ctypes.c_wchar_p]
        lib.AT_SetString.restype = ctypes.c_int

        # int AT_EXP_CONV AT_GetString(AT_H Hndl, const AT_WC* Feature,
        # AT_WC* String, int StringLength);
        lib.AT_GetString.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_int,
        ]
        lib.AT_GetString.restype = ctypes.c_int

        # int AT_EXP_CONV AT_GetStringMaxLength(AT_H Hndl,
        # const AT_WC* Feature, int* MaxStringLength);
        lib.AT_GetStringMaxLength.argtypes = [
            ctypes.c_int,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.AT_GetStringMaxLength.restype = ctypes.c_int

        # int AT_EXP_CONV AT_QueueBuffer(AT_H Hndl, AT_U8* Ptr, int PtrSize);
        lib.AT_QueueBuffer.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        lib.AT_QueueBuffer.restype = ctypes.c_int

        # int AT_EXP_CONV AT_WaitBuffer(AT_H Hndl, AT_U8** Ptr, int* PtrSize,
        # unsigned int Timeout);
        lib.AT_WaitBuffer.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_uint,
        ]
        lib.AT_WaitBuffer.restype = ctypes.c_int

        # int AT_EXP_CONV AT_Flush(AT_H Hndl);
        lib.AT_Flush.argtypes = [ctypes.c_int]
        lib.AT_Flush.restype = ctypes.c_int

        self.lib = lib
        self.intPtr = ctypes.POINTER(ctypes.c_int)
        self.boolPtr = ctypes.POINTER(ctypes.c_bool)
        self.longlongPtr = ctypes.POINTER(ctypes.c_longlong)
        self.doublePtr = ctypes.POINTER(ctypes.c_double)
        self.bufferPtr = ctypes.POINTER(ctypes.c_char_p)

    def initialiseLibrary(self):
        # int AT_EXP_CONV AT_InitialiseLibrary();
        return self._toResultEnum(self.lib.AT_InitialiseLibrary())

    def finaliseLibrary(self):
        # int AT_EXP_CONV AT_FinaliseLibrary();
        return self._toResultEnum(self.lib.AT_FinaliseLibrary())

    def open(self, cameraIndex):
        # int AT_EXP_CONV AT_Open(int CameraIndex, AT_H *Hndl);
        handle = self._getIntPtr(-1)
        result = self.lib.AT_Open(cameraIndex, handle)
        return self._toResultEnum(result), handle[0]

    def close(self, handle):
        # int AT_EXP_CONV AT_Close(AT_H Hndl);
        return self._toResultEnum(self.lib.AT_Close(handle))

    # typedef int (AT_EXP_CONV *FeatureCallback)(AT_H Hndl,
    # const AT_WC* Feature, void* Context);
    # int AT_EXP_CONV AT_RegisterFeatureCallback(AT_H Hndl,
    # const AT_WC* Feature, FeatureCallback EvCallback, void* Context);
    # int AT_EXP_CONV AT_UnregisterFeatureCallback(AT_H Hndl,
    # const AT_WC* Feature, FeatureCallback EvCallback, void* Context);

    def isImplemented(self, handle, feature):
        # int AT_EXP_CONV AT_IsImplemented(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* Implemented);
        implemented = self._getBoolPtr()
        result = self.lib.AT_IsImplemented(handle, feature.name, implemented)
        return self._toResultEnum(result), implemented[0]

    def isReadable(self, handle, feature):
        # int AT_EXP_CONV AT_IsReadable(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* Readable);
        readable = self._getBoolPtr()
        result = self.lib.AT_IsReadable(handle, feature.name, readable)
        return self._toResultEnum(result), readable[0]

    def isWritable(self, handle, feature):
        # int AT_EXP_CONV AT_IsWritable(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* Writable);
        writable = self._getBoolPtr()
        result = self.lib.AT_IsWritable(handle, feature.name, writable)
        return self._toResultEnum(result), writable[0]

    def isReadOnly(self, handle, feature):
        # int AT_EXP_CONV AT_IsReadOnly(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* ReadOnly);
        readOnly = self._getBoolPtr()
        result = self.lib.AT_IsReadOnly(handle, feature.name, readOnly)
        return self._toResultEnum(result), readOnly[0]

    def setInt(self, handle, feature, value):
        # int AT_EXP_CONV AT_SetInt(AT_H Hndl, const AT_WC* Feature, AT_64
        # Value);
        return self._toResultEnum(self.lib.AT_SetInt(handle, feature.name, value))

    def getInt(self, handle, feature):
        # int AT_EXP_CONV AT_GetInt(AT_H Hndl, const AT_WC* Feature, AT_64*
        # Value);
        value = self._getLongLongPtr()
        result = self.lib.AT_GetInt(handle, feature.name, value)
        return self._toResultEnum(result), value[0]

    def getIntMax(self, handle, feature):
        # int AT_EXP_CONV AT_GetIntMax(AT_H Hndl, const AT_WC* Feature, AT_64*
        # MaxValue);
        maxValue = self._getLongLongPtr()
        result = self.lib.AT_GetIntMax(handle, feature.name, maxValue)
        return self._toResultEnum(result), maxValue[0]

    def getIntMin(self, handle, feature):
        # int AT_EXP_CONV AT_GetIntMin(AT_H Hndl, const AT_WC* Feature, AT_64*
        # MinValue);
        minValue = self._getLongLongPtr()
        result = self.lib.AT_GetIntMin(handle, feature.name, minValue)
        return self._toResultEnum(result), minValue[0]

    def setFloat(self, handle, feature, value):
        # int AT_EXP_CONV AT_SetFloat(AT_H Hndl, const AT_WC* Feature, double
        # Value);
        return self._toResultEnum(self.lib.AT_SetFloat(handle, feature.name, value))

    def getFloat(self, handle, feature):
        # int AT_EXP_CONV AT_GetFloat(AT_H Hndl, const AT_WC* Feature, double*
        # Value);
        value = self._getDoublePtr()
        result = self.lib.AT_GetFloat(handle, feature.name, value)
        return self._toResultEnum(result), value[0]

    def getFloatMax(self, handle, feature):
        # int AT_EXP_CONV AT_GetFloatMax(AT_H Hndl, const AT_WC* Feature,
        # double* MaxValue);
        maxValue = self._getDoublePtr()
        result = self.lib.AT_GetFloatMax(handle, feature.name, maxValue)
        return self._toResultEnum(result), maxValue[0]

    def getFloatMin(self, handle, feature):
        # int AT_EXP_CONV AT_GetFloatMin(AT_H Hndl, const AT_WC* Feature,
        # double* MinValue);
        minValue = self._getDoublePtr()
        result = self.lib.AT_GetFloatMin(handle, feature.name, minValue)
        return self._toResultEnum(result), minValue[0]

    def setBool(self, handle, feature, value):
        # int AT_EXP_CONV AT_SetBool(AT_H Hndl, const AT_WC* Feature, AT_BOOL
        # Value);
        return self._toResultEnum(self.lib.AT_SetBool(handle, feature.name, value))

    def getBool(self, handle, feature):
        # int AT_EXP_CONV AT_GetBool(AT_H Hndl, const AT_WC* Feature, AT_BOOL*
        # Value);
        value = self._getBoolPtr()
        result = self.lib.AT_GetBool(handle, feature.name, value)
        return self._toResultEnum(result), value[0]

    def setEnumerated(self, handle, feature, value):
        # int AT_EXP_CONV AT_SetEnumerated(AT_H Hndl, const AT_WC* Feature, int
        # Value);
        return self._toResultEnum(
            self.lib.AT_SetEnumerated(handle, feature.name, value)
        )

    def setEnumeratedString(self, handle, feature, string):
        # int AT_EXP_CONV AT_SetEnumeratedString(AT_H Hndl,
        # const AT_WC* Feature, const AT_WC* String);
        return self._toResultEnum(
            self.lib.AT_SetEnumeratedString(handle, feature.name, string)
        )

    def getEnumerated(self, handle, feature):
        # int AT_EXP_CONV AT_GetEnumerated(AT_H Hndl, const AT_WC* Feature,
        # int* Value);
        value = self._getIntPtr()
        result = self.lib.AT_GetEnumerated(handle, feature.name, value)
        return self._toResultEnum(result), value[0]

    def getEnumeratedCount(self, handle, feature):
        # int AT_EXP_CONV AT_GetEnumeratedCount(AT_H Hndl,const  AT_WC*
        # Feature, int* Count);
        count = self._getIntPtr()
        result = self.lib.AT_GetEnumeratedCount(handle, feature.name, count)
        return self._toResultEnum(result), count[0]

    def isEnumeratedIndexAvailabe(self, handle, feature, index):
        # int AT_EXP_CONV AT_IsEnumeratedIndexAvailable(AT_H Hndl,
        # const AT_WC* Feature, int Index, AT_BOOL* Available);
        available = self._getBoolPtr()
        result = self.lib.AT_IsEnumeratedIndexAvailable(
            handle, feature.name, index, available
        )
        return self._toResultEnum(result), available[0]

    def isEnumeratedIndexImplemented(self, handle, feature, index):
        # int AT_EXP_CONV AT_IsEnumeratedIndexImplemented(AT_H Hndl,
        #  const AT_WC* Feature, int Index, AT_BOOL* Implemented);
        implemented = self._getBoolPtr()
        result = self.lib.AT_IsEnumeratedIndexImplemented(
            handle, feature.name, index, implemented
        )
        return self._toResultEnum(result), implemented[0]

    def getEnumeratedString(self, handle, feature, index):
        # int AT_EXP_CONV AT_GetEnumeratedString(AT_H Hndl,
        # const AT_WC* Feature, int Index, AT_WC* String, int StringLength);
        string = self._getUnicodeBuffer()
        result = self.lib.AT_GetEnumeratedString(
            handle, feature.name, index, string, len(string)
        )
        return self._toResultEnum(result), string.value

    def setEnumIndex(self, handle, feature, value):
        # int AT_EXP_CONV AT_SetEnumIndex(AT_H Hndl, const AT_WC* Feature,
        # int Value);
        return self._toResultEnum(self.lib.AT_SetEnumIndex(handle, feature.name, value))

    def setEnumString(self, handle, feature, string):
        # int AT_EXP_CONV AT_SetEnumString(AT_H Hndl, const AT_WC* Feature,
        # const AT_WC* String);
        return self._toResultEnum(
            self.lib.AT_SetEnumString(handle, feature.name, string)
        )

    def getEnumIndex(self, handle, feature):
        # int AT_EXP_CONV AT_GetEnumIndex(AT_H Hndl, const AT_WC* Feature,
        # int* Value);
        value = self._getIntPtr()
        result = self.lib.AT_GetEnumIndex(handle, feature.name, value)
        return self._toResultEnum(result), value[0]

    def getEnumCount(self, handle, feature):
        # int AT_EXP_CONV AT_GetEnumCount(AT_H Hndl,const  AT_WC* Feature,
        # int* Count);
        count = self._getIntPtr()
        result = self.lib.AT_GetEnumCount(handle, feature.name, count)
        return self._toResultEnum(result), count[0]

    def isEnumIndexAvailable(self, handle, feature, index):
        # int AT_EXP_CONV AT_IsEnumIndexAvailable(AT_H Hndl,
        # const AT_WC* Feature, int Index, AT_BOOL* Available);
        available = self._getBoolPtr()
        result = self.lib.AT_IsEnumIndexAvailable(
            handle, feature.name, index, available
        )
        return self._toResultEnum(result), available[0]

    def isEnumIndexImplemented(self, handle, feature, index):
        # int AT_EXP_CONV AT_IsEnumIndexImplemented(AT_H Hndl,
        # const AT_WC* Feature, int Index, AT_BOOL* Implemented);
        implemented = self._getBoolPtr()
        result = self.lib.AT_IsEnumIndexImplemented(
            handle, feature.name, index, implemented
        )
        return self._toResultEnum(result), implemented[0]

    def getEnumStringByIndex(self, handle, feature, index):
        # int AT_EXP_CONV AT_GetEnumStringByIndex(AT_H Hndl,
        # const AT_WC* Feature, int Index, AT_WC* String, int StringLength);
        string = self._getUnicodeBuffer()
        result = self.lib.AT_GetEnumStringByIndex(
            handle, feature.name, index, string, len(string)
        )
        return self._toResultEnum(result), string.value

    def command(self, handle, feature):
        # int AT_EXP_CONV AT_Command(AT_H Hndl, const AT_WC* Feature);
        return self._toResultEnum(self.lib.AT_Command(handle, feature.name))

    def setString(self, handle, feature, string):
        # int AT_EXP_CONV AT_SetString(AT_H Hndl, const AT_WC* Feature, const
        # AT_WC* String);
        return self._toResultEnum(self.lib.AT_SetString(handle, feature.name, string))

    def getString(self, handle, feature):
        # int AT_EXP_CONV AT_GetString(AT_H Hndl, const AT_WC* Feature,
        # AT_WC* String, int StringLength);
        string = self._getUnicodeBuffer()
        result = self.lib.AT_GetString(handle, feature.name, string, len(string))
        return self._toResultEnum(result), string.value

    def getStringMaxLength(self, handle, feature):
        # int AT_EXP_CONV AT_GetStringMaxLength(AT_H Hndl,
        # const AT_WC* Feature, int* MaxStringLength);
        maxStringLength = self._getIntPtr()
        result = self.lib.AT_GetStringMaxLength(handle, feature.name, maxStringLength)
        return self._toResultEnum(result), maxStringLength[0]

    def queueBuffer(self, handle, bufferSize):
        # int AT_EXP_CONV AT_QueueBuffer(AT_H Hndl, AT_U8* Ptr, int PtrSize);
        buffer = self._getStringBuffer(bufferSize)
        result = self.lib.AT_QueueBuffer(handle, buffer, len(buffer))
        return self._toResultEnum(result), buffer

    def waitBuffer(self, handle, buffer, timeout=60):
        # int AT_EXP_CONV AT_WaitBuffer(AT_H Hndl, AT_U8** Ptr,
        # int* PtrSize, unsigned int Timeout);
        ctypes.POINTERSize = self._getIntPtr()
        bufferPtr = self._getBufferPtr(buffer)
        result = self.lib.AT_WaitBuffer(handle, bufferPtr, ctypes.POINTERSize, timeout)
        return self._toResultEnum(result), ctypes.POINTERSize[0]

    def flush(self, handle):
        # int AT_EXP_CONV AT_Flush(AT_H Hndl);
        return self._toResultEnum(self.lib.AT_Flush(handle))

    def _getIntPtr(self, defaultValue=0):
        return self.intPtr(ctypes.c_int(defaultValue))

    def _getBoolPtr(self, defaultValue=False):
        return self.boolPtr(ctypes.c_bool(defaultValue))

    def _getLongLongPtr(self, defaultValue=0):
        return self.longlongPtr(ctypes.c_longlong(defaultValue))

    def _getDoublePtr(self, defaultValue=0.0):
        return self.doublePtr(ctypes.c_double(defaultValue))

    def _getBufferPtr(self, buffer):
        return self.bufferPtr(buffer)

    def _getUnicodeBuffer(self, size=128):
        return ctypes.create_unicode_buffer(size)

    def _toResultEnum(self, result):
        return Results(result)

    def _getStringBuffer(self, size=128):
        return ctypes.create_string_buffer(size)


class ATError(Exception):
    def __init__(self, result: Results):
        super().__init__()
        self.result = result

    def __str__(self):
        return self.result.name


class ATLibraryNotInitialised(Exception):
    def __init__(self):
        super().__init__()


class ATDeviceNotOpenError(Exception):
    def __init__(self):
        super().__init__()


class ATBase(object):
    def __init__(self, at=None):
        if at is None:
            self.at = AT()
        else:
            self.at = at

    def _raiseIfBad(self, result: Results):
        if result != Results.Success:
            raise ATError(result)


class ATLibrary(ATBase):
    def __init__(self, at=None):
        super().__init__(at)
        self.initialised = False

    def initialiseLibrary(self):
        if not self.initialised:
            self.at.initialiseLibrary()
            self.initialised = True

    def finaliseLibrary(self):
        if self.initialised:
            self.at.finaliseLibrary()
            self.initialised = False

    def getDeviceCount(self):
        if not self.initialised:
            raise ATLibraryNotInitialised()
        result, deviceCount = self.at.getInt(1, Features.DeviceCount)
        self._raiseIfBad(result)
        return deviceCount

    def openZyla(self, cameraIndex):
        if not self.initialised:
            raise ATLibraryNotInitialised()
        device = ATZylaDevice(cameraIndex, self.at)
        return device


class ATZylaDevice(ATBase):
    def __init__(self, cameraIndex, at=None):
        super().__init__(at)
        self.handle = -1
        result, handle = self.at.open(cameraIndex)
        self._raiseIfBad(result)
        self.handle = handle

    def close(self):
        self._assertHandle()
        result = self.at.close(self.handle)
        self._raiseIfBad(result)
        self.handle = -1

    def getAccumulateCount(self):
        """Gets the current value of AccumulateCount.

        Returns
        -------
        int
            The current value of AccumulateCount.
        """
        return self._getSomethingSimple(self.at.getInt, Features.AccumulateCount)

    def setAccumulateCount(self, value):
        """Sets AccumulateCount to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to AccumulateCount.
        """
        result, minValue = self.at.getIntMin(self.handle, Features.AccumulateCount)
        result, maxValue = self.at.getIntMax(self.handle, Features.AccumulateCount)
        if value < minValue or value > maxValue:
            raise ValueError(
                f"Value ({value}) for AccumulateCount must be "
                f"between {minValue} and {maxValue}."
            )
        self._setSomethingSimple(self.at.setInt, Features.AccumulateCount, value)

    def cmdAcquisitionStart(self):
        """Send the AcquisitionStart command."""
        self._sendCommand(Features.AcquisitionStart)

    def cmdAcquisitionStop(self):
        """Send the AcquisitionStop command."""
        self._sendCommand(Features.AcquisitionStop)

    def getAOIBinning(self):
        """Gets the current value of AOIBinning.

        Returns
        -------
        str
            The current value of AOIBinning.
        """
        index = self._getSomethingSimple(self.at.getEnumerated, Features.AOIBinning)
        return self._getSomethingWithIndex(
            self.at.getEnumStringByIndex, Features.AOIBinning, index
        )

    def getAOIBinningValues(self):
        """Gets the possible values of AOIBinning.

        Returns
        -------
        str[]
            The possible values of AOIBinning.
        """
        count = self._getSomethingSimple(self.at.getEnumCount, Features.AOIBinning)
        values = []
        for i in range(count):
            values.append(
                self._getSomethingWithIndex(
                    self.at.getEnumStringByIndex, Features.AOIBinning, i
                )
            )
        return values

    def setAOIBinning(self, value):
        """Sets AOIBinning to the specified value.

        Use getAOIBinningValues() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to AOIBinning.
        """
        validValues = self.getAOIBinningValues()
        if value not in validValues:
            raise ValueError(
                f"The value {value} is not a valid value for AOIBinning. "
                f"Valid values are {validValues}."
            )
        self._setSomethingSimple(
            self.at.setEnumeratedString, Features.AOIBinning, value
        )

    def getAOIHBin(self):
        """Gets the current value of AOIHBin.

        Returns
        -------
        int
            The current value of AOIHBin.
        """
        return self._getSomethingSimple(self.at.getInt, Features.AOIHBin)

    def setAOIHBin(self, value):
        """Sets AOIHBin to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to AOIHBin.
        """
        result, minValue = self.at.getIntMin(self.handle, Features.AOIHBin)
        result, maxValue = self.at.getIntMax(self.handle, Features.AOIHBin)
        if value < minValue or value > maxValue:
            raise ValueError(
                f"Value ({value}) for AOIHBin must be between "
                f"{minValue} and {maxValue}."
            )
        self._setSomethingSimple(self.at.setInt, Features.AOIHBin, value)

    def getAOIHeight(self):
        """Gets the current value of AOIHeight.

        Returns
        -------
        int
            The current value of AOIHeight.
        """
        return self._getSomethingSimple(self.at.getInt, Features.AOIHeight)

    def setAOIHeight(self, value):
        """Sets AOIHeight to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to AOIHeight.
        """
        result, minValue = self.at.getIntMin(self.handle, Features.AOIHeight)
        result, maxValue = self.at.getIntMax(self.handle, Features.AOIHeight)
        if value < minValue or value > maxValue:
            raise ValueError(
                f"Value ({value}) for AOIHeight must be between "
                f"{minValue} and {maxValue}."
            )
        self._setSomethingSimple(self.at.setInt, Features.AOIHeight, value)

    def getAOILeft(self):
        """Gets the current value of AOILeft.

        Returns
        -------
        int
            The current value of AOILeft.
        """
        return self._getSomethingSimple(self.at.getInt, Features.AOILeft)

    def setAOILeft(self, value):
        """Sets AOILeft to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to AOILeft.
        """
        result, minValue = self.at.getIntMin(self.handle, Features.AOILeft)
        result, maxValue = self.at.getIntMax(self.handle, Features.AOILeft)
        if value < minValue or value > maxValue:
            raise ValueError(
                f"Value ({value}) for AOILeft must be between "
                f"{minValue} and {maxValue}."
            )
        self._setSomethingSimple(self.at.setInt, Features.AOILeft, value)

    def getAOIStride(self):
        """Gets the current value of AOIStride.

        Returns
        -------
        int
            The current value of AOIStride.
        """
        return self._getSomethingSimple(self.at.getInt, Features.AOIStride)

    def getAOITop(self):
        """Gets the current value of AOITop.

        Returns
        -------
        int
            The current value of AOITop.
        """
        return self._getSomethingSimple(self.at.getInt, Features.AOITop)

    def setAOITop(self, value):
        """Sets AOITop to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to AOITop.
        """
        result, minValue = self.at.getIntMin(self.handle, Features.AOITop)
        result, maxValue = self.at.getIntMax(self.handle, Features.AOITop)
        if value < minValue or value > maxValue:
            raise ValueError(
                f"Value ({value}) for AOITop must be between "
                f"{minValue} and {maxValue}."
            )
        self._setSomethingSimple(self.at.setInt, Features.AOITop, value)

    def getAOIVBin(self):
        """Gets the current value of AOIVBin.

        Returns
        -------
        int
            The current value of AOIVBin.
        """
        return self._getSomethingSimple(self.at.getInt, Features.AOIVBin)

    def setAOIVBin(self, value):
        """Sets AOIVBin to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to AOIVBin.
        """
        result, minValue = self.at.getIntMin(self.handle, Features.AOIVBin)
        result, maxValue = self.at.getIntMax(self.handle, Features.AOIVBin)
        if value < minValue or value > maxValue:
            raise ValueError(
                f"Value ({value}) for AOIVBin must be between "
                f"{minValue} and {maxValue}."
            )
        self._setSomethingSimple(self.at.setInt, Features.AOIVBin, value)

    def getAOIWidth(self):
        """Gets the current value of AOIWidth.

        Returns
        -------
        int
            The current value of AOIWidth.
        """
        return self._getSomethingSimple(self.at.getInt, Features.AOIWidth)

    def setAOIWidth(self, value):
        """Sets AOIWidth to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to AOIWidth.
        """
        result, minValue = self.at.getIntMin(self.handle, Features.AOIWidth)
        result, maxValue = self.at.getIntMax(self.handle, Features.AOIWidth)
        if value < minValue or value > maxValue:
            raise ValueError(
                f"Value ({value}) for AOIWidth must be between "
                f"{minValue} and {maxValue}."
            )
        self._setSomethingSimple(self.at.setInt, Features.AOIWidth, value)

    def getAuxiliaryOutSource(self):
        """Gets the current value of AuxiliaryOutSource.

        Returns
        -------
        str
            The current value of AuxiliaryOutSource.
        """
        index = self._getSomethingSimple(
            self.at.getEnumerated, Features.AuxiliaryOutSource
        )
        return self._getSomethingWithIndex(
            self.at.getEnumStringByIndex, Features.AuxiliaryOutSource, index
        )

    def getAuxiliaryOutSourceValues(self):
        """Gets the possible values of AuxiliaryOutSource.

        Returns
        -------
        str[]
            The possible values of AuxiliaryOutSource.
        """
        count = self._getSomethingSimple(
            self.at.getEnumCount, Features.AuxiliaryOutSource
        )
        values = []
        for i in range(count):
            values.append(
                self._getSomethingWithIndex(
                    self.at.getEnumStringByIndex, Features.AuxiliaryOutSource, i
                )
            )
        return values

    def setAuxiliaryOutSource(self, value):
        """Sets AuxiliaryOutSource to the specified value.

        Use getAuxiliaryOutSourceValues() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to AuxiliaryOutSource.
        """
        validValues = self.getAuxiliaryOutSourceValues()
        if value not in validValues:
            raise ValueError(
                f"The value {value} is not a valid value for "
                f"AuxiliaryOutSource. Valid values are {validValues}."
            )
        self._setSomethingSimple(
            self.at.setEnumeratedString, Features.AuxiliaryOutSource, value
        )

    def getAuxOutSourceTwo(self):
        """Gets the current value of AuxOutSourceTwo.

        Returns
        -------
        str
            The current value of AuxOutSourceTwo.
        """
        index = self._getSomethingSimple(
            self.at.getEnumerated, Features.AuxOutSourceTwo
        )
        return self._getSomethingWithIndex(
            self.at.getEnumStringByIndex, Features.AuxOutSourceTwo, index
        )

    def getAuxOutSourceTwoValues(self):
        """Gets the possible values of AuxOutSourceTwo.

        Returns
        -------
        str[]
            The possible values of AuxOutSourceTwo.
        """
        count = self._getSomethingSimple(self.at.getEnumCount, Features.AuxOutSourceTwo)
        values = []
        for i in range(count):
            values.append(
                self._getSomethingWithIndex(
                    self.at.getEnumStringByIndex, Features.AuxOutSourceTwo, i
                )
            )
        return values

    def setAuxOutSourceTwo(self, value):
        """Sets AuxOutSourceTwo to the specified value.

        Use getAuxOutSourceTwoValues() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to AuxOutSourceTwo.
        """
        validValues = self.getAuxOutSourceTwoValues()
        if value not in validValues:
            raise ValueError(
                f"The value {value} is not a valid value for "
                f"AuxOutSourceTwo. Valid values are {validValues}."
            )
        self._setSomethingSimple(
            self.at.setEnumeratedString, Features.AuxOutSourceTwo, value
        )

    def getBaseline(self):
        """Gets the current value of Baseline.

        Returns
        -------
        int
            The current value of Baseline.
        """
        return self._getSomethingSimple(self.at.getInt, Features.Baseline)

    def getBitDepth(self):
        """Gets the current value of BitDepth.

        Returns
        -------
        str
            The current value of BitDepth.
        """
        index = self._getSomethingSimple(self.at.getEnumerated, Features.BitDepth)
        return self._getSomethingWithIndex(
            self.at.getEnumStringByIndex, Features.BitDepth, index
        )

    def getBitDepthValues(self):
        """Gets the possible values of BitDepth.

        Returns
        -------
        str[]
            The possible values of BitDepth.
        """
        count = self._getSomethingSimple(self.at.getEnumCount, Features.BitDepth)
        values = []
        for i in range(count):
            values.append(
                self._getSomethingWithIndex(
                    self.at.getEnumStringByIndex, Features.BitDepth, i
                )
            )
        return values

    def getBytesPerPixel(self):
        """Gets the current value of BytesPerPixel.

        Returns
        -------
        float
            The current value of BytesPerPixel.
        """
        return self._getSomethingSimple(self.at.getFloat, Features.BytesPerPixel)

    def getCameraAcquiring(self):
        """Gets the current value of CameraAcquiring.

        Returns
        -------
        bool
            The current value of CameraAcquiring.
        """
        return self._getSomethingSimple(self.at.getBool, Features.CameraAcquiring)

    def getCameraModel(self):
        """Gets the current value of CameraModel.

        Returns
        -------
        str
            The current value of CameraModel.
        """
        return self._getSomethingSimple(self.at.getString, Features.CameraModel)

    def getCameraName(self):
        """Gets the current value of CameraName.

        Returns
        -------
        str
            The current value of CameraName.
        """
        return self._getSomethingSimple(self.at.getString, Features.CameraName)

    def getCameraPresent(self):
        """Gets the current value of CameraPresent.

        Returns
        -------
        bool
            The current value of CameraPresent.
        """
        return self._getSomethingSimple(self.at.getBool, Features.CameraPresent)

    def getControllerID(self):
        """Gets the current value of ControllerID.

        Returns
        -------
        str
            The current value of ControllerID.
        """
        return self._getSomethingSimple(self.at.getString, Features.ControllerID)

    def getFrameCount(self):
        """Gets the current value of FrameCount.

        Returns
        -------
        int
            The current value of FrameCount.
        """
        return self._getSomethingSimple(self.at.getInt, Features.FrameCount)

    def setFrameCount(self, value):
        """Sets FrameCount to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to FrameCount.
        """
        result, minValue = self.at.getIntMin(self.handle, Features.FrameCount)
        result, maxValue = self.at.getIntMax(self.handle, Features.FrameCount)
        if value < minValue or value > maxValue:
            raise ValueError(
                f"Value ({value}) for FrameCount must be between "
                f"{minValue} and {maxValue}."
            )
        self._setSomethingSimple(self.at.setInt, Features.FrameCount, value)

    def getCycleMode(self):
        """Gets the current value of CycleMode.

        Returns
        -------
        str
            The current value of CycleMode.
        """
        index = self._getSomethingSimple(self.at.getEnumerated, Features.CycleMode)
        return self._getSomethingWithIndex(
            self.at.getEnumStringByIndex, Features.CycleMode, index
        )

    def getCycleModeValues(self):
        """Gets the possible values of CycleMode.

        Returns
        -------
        str[]
            The possible values of CycleMode.
        """
        count = self._getSomethingSimple(self.at.getEnumCount, Features.CycleMode)
        values = []
        for i in range(count):
            values.append(
                self._getSomethingWithIndex(
                    self.at.getEnumStringByIndex, Features.CycleMode, i
                )
            )
        return values

    def setCycleMode(self, value):
        """Sets CycleMode to the specified value.

        Use getCycleModeValues() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to CycleMode.
        """
        validValues = self.getCycleModeValues()
        if value not in validValues:
            raise ValueError(
                f"The value {value} is not a valid value for CycleMode. "
                f"Valid values are {validValues}."
            )
        self._setSomethingSimple(self.at.setEnumeratedString, Features.CycleMode, value)

    def getElectronicShutteringMode(self):
        """Gets the current value of ElectronicShutteringMode.

        Returns
        -------
        str
            The current value of ElectronicShutteringMode.
        """
        index = self._getSomethingSimple(
            self.at.getEnumerated, Features.ElectronicShutteringMode
        )
        return self._getSomethingWithIndex(
            self.at.getEnumStringByIndex, Features.ElectronicShutteringMode, index
        )

    def getElectronicShutteringModeValues(self):
        """Gets the possible values of ElectronicShutteringMode.

        Returns
        -------
        str[]
            The possible values of ElectronicShutteringMode.
        """
        count = self._getSomethingSimple(
            self.at.getEnumCount, Features.ElectronicShutteringMode
        )
        values = []
        for i in range(count):
            values.append(
                self._getSomethingWithIndex(
                    self.at.getEnumStringByIndex, Features.ElectronicShutteringMode, i
                )
            )
        return values

    def setElectronicShutteringMode(self, value):
        """Sets ElectronicShutteringMode to the specified value.

        Use getElectronicShutteringModeValues() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to ElectronicShutteringMode.
        """
        validValues = self.getElectronicShutteringModeValues()
        if value not in validValues:
            raise ValueError(
                f"The value {value} is not a valid value for "
                f"ElectronicShutteringMode. Valid values are {validValues}."
            )
        self._setSomethingSimple(
            self.at.setEnumeratedString, Features.ElectronicShutteringMode, value
        )

    def getExposedPixelHeight(self):
        """Gets the current value of ExposedPixelHeight.

        Returns
        -------
        int
            The current value of ExposedPixelHeight.
        """
        return self._getSomethingSimple(self.at.getInt, Features.ExposedPixelHeight)

    def setExposedPixelHeight(self, value):
        """Sets ExposedPixelHeight to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to ExposedPixelHeight.
        """
        result, minValue = self.at.getIntMin(self.handle, Features.ExposedPixelHeight)
        result, maxValue = self.at.getIntMax(self.handle, Features.ExposedPixelHeight)
        if value < minValue or value > maxValue:
            raise ValueError(
                f"Value ({value}) for ExposedPixelHeight must be "
                f"between {minValue} and {maxValue}."
            )
        self._setSomethingSimple(self.at.setInt, Features.ExposedPixelHeight, value)

    def getExposureTime(self):
        """Gets the current value of ExposureTime.

        Returns
        -------
        float
            The current value of ExposureTime.
        """
        return self._getSomethingSimple(self.at.getFloat, Features.ExposureTime)

    def setExposureTime(self, value):
        """Sets ExposureTime to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : float
            The value to apply to ExposureTime.
        """
        result, minValue = self.at.getFloatMin(self.handle, Features.ExposureTime)
        result, maxValue = self.at.getFloatMax(self.handle, Features.ExposureTime)
        if value < minValue or value > maxValue:
            raise ValueError(
                f"Value ({value}) for ExposureTime must be between "
                f"{minValue} and {maxValue}."
            )
        self._setSomethingSimple(self.at.setFloat, Features.ExposureTime, value)

    def getExternalTriggerDelay(self):
        """Gets the current value of ExternalTriggerDelay.

        Returns
        -------
        float
            The current value of ExternalTriggerDelay.
        """
        return self._getSomethingSimple(self.at.getFloat, Features.ExternalTriggerDelay)

    def getFanSpeed(self):
        """Gets the current value of FanSpeed.

        Returns
        -------
        str
            The current value of FanSpeed.
        """
        index = self._getSomethingSimple(self.at.getEnumerated, Features.FanSpeed)
        return self._getSomethingWithIndex(
            self.at.getEnumStringByIndex, Features.FanSpeed, index
        )

    def getFanSpeedValues(self):
        """Gets the possible values of FanSpeed.

        Returns
        -------
        str[]
            The possible values of FanSpeed.
        """
        count = self._getSomethingSimple(self.at.getEnumCount, Features.FanSpeed)
        values = []
        for i in range(count):
            values.append(
                self._getSomethingWithIndex(
                    self.at.getEnumStringByIndex, Features.FanSpeed, i
                )
            )
        return values

    def setFanSpeed(self, value):
        """Sets FanSpeed to the specified value.

        Use getFanSpeedValues() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to FanSpeed.
        """
        validValues = self.getFanSpeedValues()
        if value not in validValues:
            raise ValueError(
                f"The value {value} is not a valid value for FanSpeed. "
                f"Valid values are {validValues}."
            )
        self._setSomethingSimple(self.at.setEnumeratedString, Features.FanSpeed, value)

    def getFirmwareVersion(self):
        """Gets the current value of FirmwareVersion.

        Returns
        -------
        str
            The current value of FirmwareVersion.
        """
        return self._getSomethingSimple(self.at.getString, Features.FirmwareVersion)

    def getFrameRate(self):
        """Gets the current value of FrameRate.

        Returns
        -------
        float
            The current value of FrameRate.
        """
        return self._getSomethingSimple(self.at.getFloat, Features.FrameRate)

    def setFrameRate(self, value):
        """Sets FrameRate to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : float
            The value to apply to FrameRate.
        """
        result, minValue = self.at.getFloatMin(self.handle, Features.FrameRate)
        result, maxValue = self.at.getFloatMax(self.handle, Features.FrameRate)
        if value < minValue or value > maxValue:
            raise ValueError(
                f"Value ({value}) for FrameRate must be between "
                f"{minValue} and {maxValue}."
            )
        self._setSomethingSimple(self.at.setFloat, Features.FrameRate, value)

    def getFullAOIControl(self):
        """Gets the current value of FullAOIControl.

        Returns
        -------
        bool
            The current value of FullAOIControl.
        """
        return self._getSomethingSimple(self.at.getBool, Features.FullAOIControl)

    def getImageSizeBytes(self):
        """Gets the current value of ImageSizeBytes.

        Returns
        -------
        int
            The current value of ImageSizeBytes.
        """
        return self._getSomethingSimple(self.at.getInt, Features.ImageSizeBytes)

    def getInterfaceType(self):
        """Gets the current value of InterfaceType.

        Returns
        -------
        str
            The current value of InterfaceType.
        """
        return self._getSomethingSimple(self.at.getString, Features.InterfaceType)

    def getIOInvert(self):
        """Gets the current value of IOInvert.

        Returns
        -------
        bool
            The current value of IOInvert.
        """
        return self._getSomethingSimple(self.at.getBool, Features.IOInvert)

    def setIOInvert(self, value):
        """Sets IOInvert to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to IOInvert.
        """
        self._setSomethingSimple(self.at.setBool, Features.IOInvert, value)

    def getIOSelector(self):
        """Gets the current value of IOSelector.

        Returns
        -------
        str
            The current value of IOSelector.
        """
        index = self._getSomethingSimple(self.at.getEnumerated, Features.IOSelector)
        return self._getSomethingWithIndex(
            self.at.getEnumStringByIndex, Features.IOSelector, index
        )

    def getIOSelectorValues(self):
        """Gets the possible values of IOSelector.

        Returns
        -------
        str[]
            The possible values of IOSelector.
        """
        count = self._getSomethingSimple(self.at.getEnumCount, Features.IOSelector)
        values = []
        for i in range(count):
            values.append(
                self._getSomethingWithIndex(
                    self.at.getEnumStringByIndex, Features.IOSelector, i
                )
            )
        return values

    def setIOSelector(self, value):
        """Sets IOSelector to the specified value.

        Use getIOSelectorValues() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to IOSelector.
        """
        validValues = self.getIOSelectorValues()
        if value not in validValues:
            raise ValueError(
                f"The value {value} is not a valid value for IOSelector. "
                f"Valid values are {validValues}."
            )
        self._setSomethingSimple(
            self.at.setEnumeratedString, Features.IOSelector, value
        )

    def getLineScanSpeed(self):
        """Gets the current value of LineScanSpeed.

        Returns
        -------
        float
            The current value of LineScanSpeed.
        """
        return self._getSomethingSimple(self.at.getFloat, Features.LineScanSpeed)

    def getMaxInterfaceTransferRate(self):
        """Gets the current value of MaxInterfaceTransferRate.

        Returns
        -------
        float
            The current value of MaxInterfaceTransferRate.
        """
        return self._getSomethingSimple(
            self.at.getFloat, Features.MaxInterfaceTransferRate
        )

    def getMetadataEnable(self):
        """Gets the current value of MetadataEnable.

        Returns
        -------
        bool
            The current value of MetadataEnable.
        """
        return self._getSomethingSimple(self.at.getBool, Features.MetadataEnable)

    def setMetadataEnable(self, value):
        """Sets MetadataEnable to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to MetadataEnable.
        """
        self._setSomethingSimple(self.at.setBool, Features.MetadataEnable, value)

    def getMetadataTimestamp(self):
        """Gets the current value of MetadataTimestamp.

        Returns
        -------
        bool
            The current value of MetadataTimestamp.
        """
        return self._getSomethingSimple(self.at.getBool, Features.MetadataTimestamp)

    def setMetadataTimestamp(self, value):
        """Sets MetadataTimestamp to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to MetadataTimestamp.
        """
        self._setSomethingSimple(self.at.setBool, Features.MetadataTimestamp, value)

    def getMetadataFrame(self):
        """Gets the current value of MetadataFrame.

        Returns
        -------
        bool
            The current value of MetadataFrame.
        """
        return self._getSomethingSimple(self.at.getBool, Features.MetadataFrame)

    def getOverlap(self):
        """Gets the current value of Overlap.

        Returns
        -------
        bool
            The current value of Overlap.
        """
        return self._getSomethingSimple(self.at.getBool, Features.Overlap)

    def setOverlap(self, value):
        """Sets Overlap to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to Overlap.
        """
        self._setSomethingSimple(self.at.setBool, Features.Overlap, value)

    def getPixelEncoding(self):
        """Gets the current value of PixelEncoding.

        Returns
        -------
        str
            The current value of PixelEncoding.
        """
        index = self._getSomethingSimple(self.at.getEnumerated, Features.PixelEncoding)
        return self._getSomethingWithIndex(
            self.at.getEnumStringByIndex, Features.PixelEncoding, index
        )

    def getPixelEncodingValues(self):
        """Gets the possible values of PixelEncoding.

        Returns
        -------
        str[]
            The possible values of PixelEncoding.
        """
        count = self._getSomethingSimple(self.at.getEnumCount, Features.PixelEncoding)
        values = []
        for i in range(count):
            values.append(
                self._getSomethingWithIndex(
                    self.at.getEnumStringByIndex, Features.PixelEncoding, i
                )
            )
        return values

    def setPixelEncoding(self, value):
        """Sets PixelEncoding to the specified value.

        Use getPixelEncodingValues() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to PixelEncoding.
        """
        validValues = self.getPixelEncodingValues()
        if value not in validValues:
            raise ValueError(
                f"The value {value} is not a valid value for "
                f"PixelEncoding. Valid values are {validValues}."
            )
        self._setSomethingSimple(
            self.at.setEnumeratedString, Features.PixelEncoding, value
        )

    def getPixelHeight(self):
        """Gets the current value of PixelHeight.

        Returns
        -------
        float
            The current value of PixelHeight.
        """
        return self._getSomethingSimple(self.at.getFloat, Features.PixelHeight)

    def getPixelReadoutRate(self):
        """Gets the current value of PixelReadoutRate.

        Returns
        -------
        str
            The current value of PixelReadoutRate.
        """
        index = self._getSomethingSimple(
            self.at.getEnumerated, Features.PixelReadoutRate
        )
        return self._getSomethingWithIndex(
            self.at.getEnumStringByIndex, Features.PixelReadoutRate, index
        )

    def getPixelReadoutRateValues(self):
        """Gets the possible values of PixelReadoutRate.

        Returns
        -------
        str[]
            The possible values of PixelReadoutRate.
        """
        count = self._getSomethingSimple(
            self.at.getEnumCount, Features.PixelReadoutRate
        )
        values = []
        for i in range(count):
            values.append(
                self._getSomethingWithIndex(
                    self.at.getEnumStringByIndex, Features.PixelReadoutRate, i
                )
            )
        return values

    def setPixelReadoutRate(self, value):
        """Sets PixelReadoutRate to the specified value.

        Use getPixelReadoutRateValues() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to PixelReadoutRate.
        """
        validValues = self.getPixelReadoutRateValues()
        if value not in validValues:
            raise ValueError(
                f"The value {value} is not a valid value for "
                f"PixelReadoutRate. Valid values are {validValues}."
            )
        self._setSomethingSimple(
            self.at.setEnumeratedString, Features.PixelReadoutRate, value
        )

    def getPixelWidth(self):
        """Gets the current value of PixelWidth.

        Returns
        -------
        float
            The current value of PixelWidth.
        """
        return self._getSomethingSimple(self.at.getFloat, Features.PixelWidth)

    def getReadoutTime(self):
        """Gets the current value of ReadoutTime.

        Returns
        -------
        float
            The current value of ReadoutTime.
        """
        return self._getSomethingSimple(self.at.getFloat, Features.ReadoutTime)

    def getRowReadTime(self):
        """Gets the current value of RowReadTime.

        Returns
        -------
        float
            The current value of RowReadTime.
        """
        return self._getSomethingSimple(self.at.getFloat, Features.RowReadTime)

    def getSensorCooling(self):
        """Gets the current value of SensorCooling.

        Returns
        -------
        bool
            The current value of SensorCooling.
        """
        return self._getSomethingSimple(self.at.getBool, Features.SensorCooling)

    def setSensorCooling(self, value):
        """Sets SensorCooling to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to SensorCooling.
        """
        self._setSomethingSimple(self.at.setBool, Features.SensorCooling, value)

    def getSensorHeight(self):
        """Gets the current value of SensorHeight.

        Returns
        -------
        int
            The current value of SensorHeight.
        """
        return self._getSomethingSimple(self.at.getInt, Features.SensorHeight)

    def getSensorTemperature(self):
        """Gets the current value of SensorTemperature.

        Returns
        -------
        float
            The current value of SensorTemperature.
        """
        return self._getSomethingSimple(self.at.getFloat, Features.SensorTemperature)

    def getSensorWidth(self):
        """Gets the current value of SensorWidth.

        Returns
        -------
        int
            The current value of SensorWidth.
        """
        return self._getSomethingSimple(self.at.getInt, Features.SensorWidth)

    def getSerialNumber(self):
        """Gets the current value of SerialNumber.

        Returns
        -------
        str
            The current value of SerialNumber.
        """
        return self._getSomethingSimple(self.at.getString, Features.SerialNumber)

    def getShutterOutputMode(self):
        """Gets the current value of ShutterOutputMode.

        Returns
        -------
        str
            The current value of ShutterOutputMode.
        """
        index = self._getSomethingSimple(
            self.at.getEnumerated, Features.ShutterOutputMode
        )
        return self._getSomethingWithIndex(
            self.at.getEnumStringByIndex, Features.ShutterOutputMode, index
        )

    def getShutterOutputModeValues(self):
        """Gets the possible values of ShutterOutputMode.

        Returns
        -------
        str[]
            The possible values of ShutterOutputMode.
        """
        count = self._getSomethingSimple(
            self.at.getEnumCount, Features.ShutterOutputMode
        )
        values = []
        for i in range(count):
            values.append(
                self._getSomethingWithIndex(
                    self.at.getEnumStringByIndex, Features.ShutterOutputMode, i
                )
            )
        return values

    def setShutterOutputMode(self, value):
        """Sets ShutterOutputMode to the specified value.

        Use getShutterOutputModeValues() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to ShutterOutputMode.
        """
        validValues = self.getShutterOutputModeValues()
        if value not in validValues:
            raise ValueError(
                f"The value {value} is not a valid value for ShutterOutputMode. Valid "
                f"values are {validValues}."
            )
        self._setSomethingSimple(
            self.at.setEnumeratedString, Features.ShutterOutputMode, value
        )

    def getSimplePreAmpGainControl(self):
        """Gets the current value of SimplePreAmpGainControl.

        Returns
        -------
        str
            The current value of SimplePreAmpGainControl.
        """
        index = self._getSomethingSimple(
            self.at.getEnumerated, Features.SimplePreAmpGainControl
        )
        return self._getSomethingWithIndex(
            self.at.getEnumStringByIndex, Features.SimplePreAmpGainControl, index
        )

    def getSimplePreAmpGainControlValues(self):
        """Gets the possible values of SimplePreAmpGainControl.

        Returns
        -------
        str[]
            The possible values of SimplePreAmpGainControl.
        """
        count = self._getSomethingSimple(
            self.at.getEnumCount, Features.SimplePreAmpGainControl
        )
        values = []
        for i in range(count):
            values.append(
                self._getSomethingWithIndex(
                    self.at.getEnumStringByIndex, Features.SimplePreAmpGainControl, i
                )
            )
        return values

    def setSimplePreAmpGainControl(self, value):
        """Sets SimplePreAmpGainControl to the specified value.

        Use getSimplePreAmpGainControlValues() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to SimplePreAmpGainControl.
        """
        validValues = self.getSimplePreAmpGainControlValues()
        if value not in validValues:
            raise ValueError(
                f"The value {value} is not a valid value for "
                f"SimplePreAmpGainControl. Valid values are {validValues}."
            )
        self._setSomethingSimple(
            self.at.setEnumeratedString, Features.SimplePreAmpGainControl, value
        )

    def getShutterTransferTime(self):
        """Gets the current value of ShutterTransferTime.

        Returns
        -------
        float
            The current value of ShutterTransferTime.
        """
        return self._getSomethingSimple(self.at.getFloat, Features.ShutterTransferTime)

    def setShutterTransferTime(self, value):
        """Sets ShutterTransferTime to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : float
            The value to apply to ShutterTransferTime.
        """
        result, minValue = self.at.getFloatMin(
            self.handle, Features.ShutterTransferTime
        )
        result, maxValue = self.at.getFloatMax(
            self.handle, Features.ShutterTransferTime
        )
        if value < minValue or value > maxValue:
            raise ValueError(
                f"Value ({value}) for ShutterTransferTime must be"
                f" between {minValue} and {maxValue}."
            )
        self._setSomethingSimple(self.at.setFloat, Features.ShutterTransferTime, value)

    def cmdSoftwareTrigger(self):
        """Send the SoftwareTrigger command."""
        self._sendCommand(Features.SoftwareTrigger)

    def getStaticBlemishCorrection(self):
        """Gets the current value of StaticBlemishCorrection.

        Returns
        -------
        bool
            The current value of StaticBlemishCorrection.
        """
        return self._getSomethingSimple(
            self.at.getBool, Features.StaticBlemishCorrection
        )

    def setStaticBlemishCorrection(self, value):
        """Sets StaticBlemishCorrection to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to StaticBlemishCorrection.
        """
        self._setSomethingSimple(
            self.at.setBool, Features.StaticBlemishCorrection, value
        )

    def getSpuriousNoiseFilter(self):
        """Gets the current value of SpuriousNoiseFilter.

        Returns
        -------
        bool
            The current value of SpuriousNoiseFilter.
        """
        return self._getSomethingSimple(self.at.getBool, Features.SpuriousNoiseFilter)

    def setSpuriousNoiseFilter(self, value):
        """Sets SpuriousNoiseFilter to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to SpuriousNoiseFilter.
        """
        self._setSomethingSimple(self.at.setBool, Features.SpuriousNoiseFilter, value)

    def getTargetSensorTemperature(self):
        """Gets the current value of TargetSensorTemperature.

        Returns
        -------
        float
            The current value of TargetSensorTemperature.
        """
        return self._getSomethingSimple(
            self.at.getFloat, Features.TargetSensorTemperature
        )

    def getTemperatureControl(self):
        """Gets the current value of TemperatureControl.

        Returns
        -------
        str
            The current value of TemperatureControl.
        """
        index = self._getSomethingSimple(
            self.at.getEnumerated, Features.TemperatureControl
        )
        return self._getSomethingWithIndex(
            self.at.getEnumStringByIndex, Features.TemperatureControl, index
        )

    def getTemperatureControlValues(self):
        """Gets the possible values of TemperatureControl.

        Returns
        -------
        str[]
            The possible values of TemperatureControl.
        """
        count = self._getSomethingSimple(
            self.at.getEnumCount, Features.TemperatureControl
        )
        values = []
        for i in range(count):
            values.append(
                self._getSomethingWithIndex(
                    self.at.getEnumStringByIndex, Features.TemperatureControl, i
                )
            )
        return values

    def getTemperatureStatus(self):
        """Gets the current value of TemperatureStatus.

        Returns
        -------
        str
            The current value of TemperatureStatus.
        """
        index = self._getSomethingSimple(
            self.at.getEnumerated, Features.TemperatureStatus
        )
        return self._getSomethingWithIndex(
            self.at.getEnumStringByIndex, Features.TemperatureStatus, index
        )

    def getTemperatureStatusValues(self):
        """Gets the possible values of TemperatureStatus.

        Returns
        -------
        str[]
            The possible values of TemperatureStatus.
        """
        count = self._getSomethingSimple(
            self.at.getEnumCount, Features.TemperatureStatus
        )
        values = []
        for i in range(count):
            values.append(
                self._getSomethingWithIndex(
                    self.at.getEnumStringByIndex, Features.TemperatureStatus, i
                )
            )
        return values

    def getTimestampClock(self):
        """Gets the current value of TimestampClock.

        Returns
        -------
        int
            The current value of TimestampClock.
        """
        return self._getSomethingSimple(self.at.getInt, Features.TimestampClock)

    def getTimestampClockFrequency(self):
        """Gets the current value of TimestampClockFrequency.

        Returns
        -------
        int
            The current value of TimestampClockFrequency.
        """
        return self._getSomethingSimple(
            self.at.getInt, Features.TimestampClockFrequency
        )

    def getTriggerMode(self):
        """Gets the current value of TriggerMode.

        Returns
        -------
        str
            The current value of TriggerMode.
        """
        index = self._getSomethingSimple(self.at.getEnumerated, Features.TriggerMode)
        return self._getSomethingWithIndex(
            self.at.getEnumStringByIndex, Features.TriggerMode, index
        )

    def getTriggerModeValues(self):
        """Gets the possible values of TriggerMode.

        Returns
        -------
        str[]
            The possible values of TriggerMode.
        """
        count = self._getSomethingSimple(self.at.getEnumCount, Features.TriggerMode)
        values = []
        for i in range(count):
            values.append(
                self._getSomethingWithIndex(
                    self.at.getEnumStringByIndex, Features.TriggerMode, i
                )
            )
        return values

    def setTriggerMode(self, value):
        """Sets TriggerMode to the specified value.

        Use getTriggerModeValues() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to TriggerMode.
        """
        validValues = self.getTriggerModeValues()
        if value not in validValues:
            raise ValueError(
                f"The value {value} is not a valid value for TriggerMode. "
                f"Valid values are {validValues}."
            )
        self._setSomethingSimple(
            self.at.setEnumeratedString, Features.TriggerMode, value
        )

    def getVerticallyCentreAOI(self):
        """Gets the current value of VerticallyCentreAOI.

        Returns
        -------
        bool
            The current value of VerticallyCentreAOI.
        """
        return self._getSomethingSimple(self.at.getBool, Features.VerticallyCentreAOI)

    def setVerticallyCentreAOI(self, value):
        """Sets VerticallyCentreAOI to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to VerticallyCentreAOI.
        """
        self._setSomethingSimple(self.at.setBool, Features.VerticallyCentreAOI, value)

    def queueBuffer(self):
        """Adds a data buffer to the internal driver queue.

        Returns
        -------
        ctypes.c_char_p
            The buffer added to the queue.
        """
        self._assertHandle()
        result, buffer = self.at.queueBuffer(self.handle, self.getImageSizeBytes())
        self._raiseIfBad(result)
        return buffer

    def waitBuffer(self, buffer, timeout=60000):
        """Waits for a data buffer to be populated during image acquisition.

        Parameters
        ----------
        buffer : ctypes.c_char_p
            The buffer that has already been added to the queue.

        Returns
        -------
        int
            The number of bytes populated in the buffer."""
        self._assertHandle()
        result, bytesPopulated = self.at.waitBuffer(self.handle, buffer, timeout)
        self._raiseIfBad(result)
        return bytesPopulated

    def flush(self):
        """Flushes the current data buffer queue."""
        self._assertHandle()
        result = self.at.flush(self.handle)
        self._raiseIfBad(result)

    def take(self, frameCount):
        self.flush()
        self.setFrameCount(frameCount)
        buffers = []
        for i in range(frameCount):
            buffers.append(self.queueBuffer())
        self.cmdAcquisitionStart()
        for buffer in buffers:
            self.waitBuffer(buffer)
        return buffers

    def takeOne(self):
        self.flush()
        buffer = self.queueBuffer()
        self.cmdAcquisitionStart()
        self.waitBuffer(buffer)
        return buffer

    def _setSomethingSimple(self, action, feature, value):
        self._assertHandle()
        result = action(self.handle, feature, value)
        self._raiseIfBad(result)

    def _getSomethingSimple(self, action, feature):
        self._assertHandle()
        result, something = action(self.handle, feature)
        self._raiseIfBad(result)
        return something

    def _getSomethingWithIndex(self, action, feature, index):
        self._assertHandle()
        result, something = action(self.handle, feature, index)
        self._raiseIfBad(result)
        return something

    def _sendCommand(self, feature):
        self._assertHandle()
        result = self.at.command(self.handle, feature)
        self._raiseIfBad(result)

    def _assertHandle(self):
        if self.handle == -1:
            raise ATDeviceNotOpenError()
