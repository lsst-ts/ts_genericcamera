# This file is part of ts_genericcamera.
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
import ctypes
from ctypes.util import find_library
import enum
import struct

import numpy as np
import yaml

from .basecamera import BaseCamera
from ..exposure import Exposure


class AndorCamera(BaseCamera):
    def __init__(self, log=None):
        super().__init__(log)
        self.lib = ATLibrary()
        self.lib.initialiseLibrary()
        self.is_live_exposure = False
        self.id = 0
        self.accumulate_count = 1
        self.binValue = 1
        self.normal_image_type = None
        self.current_image_type = None
        self.dev = None

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
        self.accumulate_count = 1
        self.binValue = 1
        self.normal_image_type = "mono16"
        self.current_image_type = self.normal_image_type
        self.dev = self.lib.open_zyla(self.id)

    def get_config_schema(self):
        return yaml.safe_load(
            """
$schema: http://json-schema.org/draft-07/schema#
description: Schema for Andor cameras.
type: object
properties:
  id:
    default: 0
    type: number
    description: The ID of the camera to be set in the FITS header.
  accumulate_count:
    default: 1
    type: number
    description: The number of images to take.
  bin_value:
    default: 1
    type: number
  image_type:
    default: mono16
    type: string
    enum:
      - mono12
      - mono12_packed
      - mono16
      - mono32
"""
        )

    def get_make_and_model(self):
        """Get the make and model of the camera.

        Returns
        -------
        str
            The make and model of the camera."""
        return self.dev.getCameraModel() + " " + self.dev.getCameraName()

    def set_roi(self, top, left, width, height):
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

    def get_roi(self):
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

    def set_full_frame(self):
        """Sets the region of interest to the whole sensor."""
        result, width = self.dev.at.getIntMax(self.dev.handle, Features.AOIWidth)
        result, height = self.dev.at.getIntMax(self.dev.handle, Features.AOIHeight)
        self.setROI(0, 0, width, height)

    def set_exposure_time(self, duration):
        """Sets the exposure time.

        Parameters
        ----------
        duration : float
            The exposure time in seconds."""
        self.dev.setExposureTime(duration)

    def configure_for_live_view(self):
        """Configure the camera for live view.

        This should change the image format to 8bits per pixel so
        the image can be encoded to JPEG."""
        self.is_live_exposure = True

    def configure_for_exposure(self):
        """Configure the camera for a standard exposure."""
        self.is_live_exposure = False

    async def take_exposure(self):
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
        bytes_received = 0
        while bytes_received == 0:
            try:
                bytes_received = self.dev.waitBuffer(buffer, 0)
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
        if self.is_live_exposure:
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
        self.int_ptr = ctypes.POINTER(ctypes.c_int)
        self.bool_ptr = ctypes.POINTER(ctypes.c_bool)
        self.long_long_ptr = ctypes.POINTER(ctypes.c_longlong)
        self.double_ptr = ctypes.POINTER(ctypes.c_double)
        self.buffer_ptr = ctypes.POINTER(ctypes.c_char_p)

    @api
    def initialiseLibrary(self):
        # int AT_EXP_CONV AT_InitialiseLibrary();
        return self._to_result_enum(self.lib.AT_InitialiseLibrary())

    @api
    def finaliseLibrary(self):
        # int AT_EXP_CONV AT_FinaliseLibrary();
        return self._to_result_enum(self.lib.AT_FinaliseLibrary())

    def open(self, camera_index):
        # int AT_EXP_CONV AT_Open(int CameraIndex, AT_H *Hndl);
        handle = self._get_int_ptr(-1)
        result = self.lib.AT_Open(camera_index, handle)
        return self._to_result_enum(result), handle[0]

    def close(self, handle):
        # int AT_EXP_CONV AT_Close(AT_H Hndl);
        return self._to_result_enum(self.lib.AT_Close(handle))

    # typedef int (AT_EXP_CONV *FeatureCallback)(AT_H Hndl,
    # const AT_WC* Feature, void* Context);
    # int AT_EXP_CONV AT_RegisterFeatureCallback(AT_H Hndl,
    # const AT_WC* Feature, FeatureCallback EvCallback, void* Context);
    # int AT_EXP_CONV AT_UnregisterFeatureCallback(AT_H Hndl,
    # const AT_WC* Feature, FeatureCallback EvCallback, void* Context);

    @api
    def isImplemented(self, handle, feature):
        # int AT_EXP_CONV AT_IsImplemented(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* Implemented);
        implemented = self._get_bool_ptr()
        result = self.lib.AT_IsImplemented(handle, feature.name, implemented)
        return self._to_result_enum(result), implemented[0]

    @api
    def isReadable(self, handle, feature):
        # int AT_EXP_CONV AT_IsReadable(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* Readable);
        readable = self._get_bool_ptr()
        result = self.lib.AT_IsReadable(handle, feature.name, readable)
        return self._to_result_enum(result), readable[0]

    @api
    def isWritable(self, handle, feature):
        # int AT_EXP_CONV AT_IsWritable(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* Writable);
        writable = self._get_bool_ptr()
        result = self.lib.AT_IsWritable(handle, feature.name, writable)
        return self._to_result_enum(result), writable[0]

    @api
    def isReadOnly(self, handle, feature):
        # int AT_EXP_CONV AT_IsReadOnly(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* ReadOnly);
        readOnly = self._get_bool_ptr()
        result = self.lib.AT_IsReadOnly(handle, feature.name, readOnly)
        return self._to_result_enum(result), readOnly[0]

    @api
    def setInt(self, handle, feature, value):
        # int AT_EXP_CONV AT_SetInt(AT_H Hndl, const AT_WC* Feature, AT_64
        # Value);
        return self._to_result_enum(self.lib.AT_SetInt(handle, feature.name, value))

    @api
    def getInt(self, handle, feature):
        # int AT_EXP_CONV AT_GetInt(AT_H Hndl, const AT_WC* Feature, AT_64*
        # Value);
        value = self._get_long_long_ptr()
        result = self.lib.AT_GetInt(handle, feature.name, value)
        return self._to_result_enum(result), value[0]

    @api
    def getIntMax(self, handle, feature):
        # int AT_EXP_CONV AT_GetIntMax(AT_H Hndl, const AT_WC* Feature, AT_64*
        # MaxValue);
        maxValue = self._get_long_long_ptr()
        result = self.lib.AT_GetIntMax(handle, feature.name, maxValue)
        return self._to_result_enum(result), maxValue[0]

    @api
    def getIntMin(self, handle, feature):
        # int AT_EXP_CONV AT_GetIntMin(AT_H Hndl, const AT_WC* Feature, AT_64*
        # MinValue);
        minValue = self._get_long_long_ptr()
        result = self.lib.AT_GetIntMin(handle, feature.name, minValue)
        return self._to_result_enum(result), minValue[0]

    @api
    def setFloat(self, handle, feature, value):
        # int AT_EXP_CONV AT_SetFloat(AT_H Hndl, const AT_WC* Feature, double
        # Value);
        return self._to_result_enum(self.lib.AT_SetFloat(handle, feature.name, value))

    @api
    def getFloat(self, handle, feature):
        # int AT_EXP_CONV AT_GetFloat(AT_H Hndl, const AT_WC* Feature, double*
        # Value);
        value = self._get_double_ptr()
        result = self.lib.AT_GetFloat(handle, feature.name, value)
        return self._to_result_enum(result), value[0]

    @api
    def getFloatMax(self, handle, feature):
        # int AT_EXP_CONV AT_GetFloatMax(AT_H Hndl, const AT_WC* Feature,
        # double* MaxValue);
        maxValue = self._get_double_ptr()
        result = self.lib.AT_GetFloatMax(handle, feature.name, maxValue)
        return self._to_result_enum(result), maxValue[0]

    @api
    def getFloatMin(self, handle, feature):
        # int AT_EXP_CONV AT_GetFloatMin(AT_H Hndl, const AT_WC* Feature,
        # double* MinValue);
        minValue = self._get_double_ptr()
        result = self.lib.AT_GetFloatMin(handle, feature.name, minValue)
        return self._to_result_enum(result), minValue[0]

    @api
    def setBool(self, handle, feature, value):
        # int AT_EXP_CONV AT_SetBool(AT_H Hndl, const AT_WC* Feature, AT_BOOL
        # Value);
        return self._to_result_enum(self.lib.AT_SetBool(handle, feature.name, value))

    @api
    def getBool(self, handle, feature):
        # int AT_EXP_CONV AT_GetBool(AT_H Hndl, const AT_WC* Feature, AT_BOOL*
        # Value);
        value = self._get_bool_ptr()
        result = self.lib.AT_GetBool(handle, feature.name, value)
        return self._to_result_enum(result), value[0]

    @api
    def setEnumerated(self, handle, feature, value):
        # int AT_EXP_CONV AT_SetEnumerated(AT_H Hndl, const AT_WC* Feature, int
        # Value);
        return self._to_result_enum(
            self.lib.AT_SetEnumerated(handle, feature.name, value)
        )

    @api
    def setEnumeratedString(self, handle, feature, string):
        # int AT_EXP_CONV AT_SetEnumeratedString(AT_H Hndl,
        # const AT_WC* Feature, const AT_WC* String);
        return self._to_result_enum(
            self.lib.AT_SetEnumeratedString(handle, feature.name, string)
        )

    @api
    def getEnumerated(self, handle, feature):
        # int AT_EXP_CONV AT_GetEnumerated(AT_H Hndl, const AT_WC* Feature,
        # int* Value);
        value = self._get_int_ptr()
        result = self.lib.AT_GetEnumerated(handle, feature.name, value)
        return self._to_result_enum(result), value[0]

    @api
    def getEnumeratedCount(self, handle, feature):
        # int AT_EXP_CONV AT_GetEnumeratedCount(AT_H Hndl,const  AT_WC*
        # Feature, int* Count);
        count = self._get_int_ptr()
        result = self.lib.AT_GetEnumeratedCount(handle, feature.name, count)
        return self._to_result_enum(result), count[0]

    @api
    def isEnumeratedIndexAvailabe(self, handle, feature, index):
        # int AT_EXP_CONV AT_IsEnumeratedIndexAvailable(AT_H Hndl,
        # const AT_WC* Feature, int Index, AT_BOOL* Available);
        available = self._get_bool_ptr()
        result = self.lib.AT_IsEnumeratedIndexAvailable(
            handle, feature.name, index, available
        )
        return self._to_result_enum(result), available[0]

    @api
    def isEnumeratedIndexImplemented(self, handle, feature, index):
        # int AT_EXP_CONV AT_IsEnumeratedIndexImplemented(AT_H Hndl,
        #  const AT_WC* Feature, int Index, AT_BOOL* Implemented);
        implemented = self._get_bool_ptr()
        result = self.lib.AT_IsEnumeratedIndexImplemented(
            handle, feature.name, index, implemented
        )
        return self._to_result_enum(result), implemented[0]

    @api
    def getEnumeratedString(self, handle, feature, index):
        # int AT_EXP_CONV AT_GetEnumeratedString(AT_H Hndl,
        # const AT_WC* Feature, int Index, AT_WC* String, int StringLength);
        string = self._get_unicode_buffer()
        result = self.lib.AT_GetEnumeratedString(
            handle, feature.name, index, string, len(string)
        )
        return self._to_result_enum(result), string.value

    @api
    def setEnumIndex(self, handle, feature, value):
        # int AT_EXP_CONV AT_SetEnumIndex(AT_H Hndl, const AT_WC* Feature,
        # int Value);
        return self._to_result_enum(self.lib.AT_SetEnumIndex(handle, feature.name, value))

    @api
    def setEnumString(self, handle, feature, string):
        # int AT_EXP_CONV AT_SetEnumString(AT_H Hndl, const AT_WC* Feature,
        # const AT_WC* String);
        return self._to_result_enum(
            self.lib.AT_SetEnumString(handle, feature.name, string)
        )

    @api
    def getEnumIndex(self, handle, feature):
        # int AT_EXP_CONV AT_GetEnumIndex(AT_H Hndl, const AT_WC* Feature,
        # int* Value);
        value = self._get_int_ptr()
        result = self.lib.AT_GetEnumIndex(handle, feature.name, value)
        return self._to_result_enum(result), value[0]

    @api
    def getEnumCount(self, handle, feature):
        # int AT_EXP_CONV AT_GetEnumCount(AT_H Hndl,const  AT_WC* Feature,
        # int* Count);
        count = self._get_int_ptr()
        result = self.lib.AT_GetEnumCount(handle, feature.name, count)
        return self._to_result_enum(result), count[0]

    @api
    def isEnumIndexAvailable(self, handle, feature, index):
        # int AT_EXP_CONV AT_IsEnumIndexAvailable(AT_H Hndl,
        # const AT_WC* Feature, int Index, AT_BOOL* Available);
        available = self._get_bool_ptr()
        result = self.lib.AT_IsEnumIndexAvailable(
            handle, feature.name, index, available
        )
        return self._to_result_enum(result), available[0]

    @api
    def isEnumIndexImplemented(self, handle, feature, index):
        # int AT_EXP_CONV AT_IsEnumIndexImplemented(AT_H Hndl,
        # const AT_WC* Feature, int Index, AT_BOOL* Implemented);
        implemented = self._get_bool_ptr()
        result = self.lib.AT_IsEnumIndexImplemented(
            handle, feature.name, index, implemented
        )
        return self._to_result_enum(result), implemented[0]

    @api
    def getEnumStringByIndex(self, handle, feature, index):
        # int AT_EXP_CONV AT_GetEnumStringByIndex(AT_H Hndl,
        # const AT_WC* Feature, int Index, AT_WC* String, int StringLength);
        string = self._get_unicode_buffer()
        result = self.lib.AT_GetEnumStringByIndex(
            handle, feature.name, index, string, len(string)
        )
        return self._to_result_enum(result), string.value

    def command(self, handle, feature):
        # int AT_EXP_CONV AT_Command(AT_H Hndl, const AT_WC* Feature);
        return self._to_result_enum(self.lib.AT_Command(handle, feature.name))

    @api
    def setString(self, handle, feature, string):
        # int AT_EXP_CONV AT_SetString(AT_H Hndl, const AT_WC* Feature, const
        # AT_WC* String);
        return self._to_result_enum(self.lib.AT_SetString(handle, feature.name, string))

    @api
    def getString(self, handle, feature):
        # int AT_EXP_CONV AT_GetString(AT_H Hndl, const AT_WC* Feature,
        # AT_WC* String, int StringLength);
        string = self._get_unicode_buffer()
        result = self.lib.AT_GetString(handle, feature.name, string, len(string))
        return self._to_result_enum(result), string.value

    @api
    def getStringMaxLength(self, handle, feature):
        # int AT_EXP_CONV AT_GetStringMaxLength(AT_H Hndl,
        # const AT_WC* Feature, int* MaxStringLength);
        maxStringLength = self._get_int_ptr()
        result = self.lib.AT_GetStringMaxLength(handle, feature.name, maxStringLength)
        return self._to_result_enum(result), maxStringLength[0]

    @api
    def queueBuffer(self, handle, buffer_size):
        # int AT_EXP_CONV AT_QueueBuffer(AT_H Hndl, AT_U8* Ptr, int PtrSize);
        buffer = self._get_string_buffer(buffer_size)
        result = self.lib.AT_QueueBuffer(handle, buffer, len(buffer))
        return self._to_result_enum(result), buffer

    @api
    def waitBuffer(self, handle, buffer, timeout=60):
        # int AT_EXP_CONV AT_WaitBuffer(AT_H Hndl, AT_U8** Ptr,
        # int* PtrSize, unsigned int Timeout);
        ctypes.POINTERSize = self._get_int_ptr()
        buffer_ptr = self._get_buffer_ptr(buffer)
        result = self.lib.AT_WaitBuffer(handle, buffer_ptr, ctypes.POINTERSize, timeout)
        return self._to_result_enum(result), ctypes.POINTERSize[0]

    def flush(self, handle):
        # int AT_EXP_CONV AT_Flush(AT_H Hndl);
        return self._to_result_enum(self.lib.AT_Flush(handle))

    def _get_int_ptr(self, default_value=0):
        return self.int_ptr(ctypes.c_int(default_value))

    def _get_bool_ptr(self, default_value=False):
        return self.bool_ptr(ctypes.c_bool(default_value))

    def _get_long_long_ptr(self, default_value=0):
        return self.long_long_ptr(ctypes.c_longlong(default_value))

    def _get_double_ptr(self, default_value=0.0):
        return self.double_ptr(ctypes.c_double(default_value))

    def _get_buffer_ptr(self, buffer):
        return self.buffer_ptr(buffer)

    def _get_unicode_buffer(self, size=128):
        return ctypes.create_unicode_buffer(size)

    def _to_result_enum(self, result):
        return Results(result)

    def _get_string_buffer(self, size=128):
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

    def _raise_if_bad(self, result: Results):
        if result != Results.Success:
            raise ATError(result)


class ATLibrary(ATBase):
    def __init__(self, at=None):
        super().__init__(at)
        self.initialised = False

    @api
    def initialiseLibrary(self):
        if not self.initialised:
            self.at.initialiseLibrary()
            self.initialised = True

    @api
    def finaliseLibrary(self):
        if self.initialised:
            self.at.finaliseLibrary()
            self.initialised = False

    @api
    def getDeviceCount(self):
        if not self.initialised:
            raise ATLibraryNotInitialised()
        result, deviceCount = self.at.getInt(1, Features.DeviceCount)
        self._raise_if_bad(result)
        return deviceCount

    def open_zyla(self, camera_index):
        if not self.initialised:
            raise ATLibraryNotInitialised()
        device = ATZylaDevice(camera_index, self.at)
        return device


class ATZylaDevice(ATBase):
    def __init__(self, camera_index, at=None):
        super().__init__(at)
        self.handle = -1
        result, handle = self.at.open(camera_index)
        self._raise_if_bad(result)
        self.handle = handle

    def close(self):
        self._assert_handle()
        result = self.at.close(self.handle)
        self._raise_if_bad(result)
        self.handle = -1

    @api
    def getAccumulateCount(self):
        """Gets the current value of AccumulateCount.

        Returns
        -------
        int
            The current value of AccumulateCount.
        """
        return self._get_something_simple(self.at.getInt, Features.AccumulateCount)

    @api
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
        self._set_something_simple(self.at.setInt, Features.AccumulateCount, value)

    @api
    def cmdAcquisitionStart(self):
        """Send the AcquisitionStart command."""
        self._send_command(Features.AcquisitionStart)

    @api
    def cmdAcquisitionStop(self):
        """Send the AcquisitionStop command."""
        self._send_command(Features.AcquisitionStop)

    @api
    def getAOIBinning(self):
        """Gets the current value of AOIBinning.

        Returns
        -------
        str
            The current value of AOIBinning.
        """
        index = self._get_something_simple(self.at.getEnumerated, Features.AOIBinning)
        return self._get_something_with_index(
            self.at.getEnumStringByIndex, Features.AOIBinning, index
        )

    @api
    def getAOIBinningValues(self):
        """Gets the possible values of AOIBinning.

        Returns
        -------
        str[]
            The possible values of AOIBinning.
        """
        count = self._get_something_simple(self.at.getEnumCount, Features.AOIBinning)
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.getEnumStringByIndex, Features.AOIBinning, i
                )
            )
        return values

    @api
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
        self._set_something_simple(
            self.at.setEnumeratedString, Features.AOIBinning, value
        )

    @api
    def getAOIHBin(self):
        """Gets the current value of AOIHBin.

        Returns
        -------
        int
            The current value of AOIHBin.
        """
        return self._get_something_simple(self.at.getInt, Features.AOIHBin)

    @api
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
        self._set_something_simple(self.at.setInt, Features.AOIHBin, value)

    @api
    def getAOIHeight(self):
        """Gets the current value of AOIHeight.

        Returns
        -------
        int
            The current value of AOIHeight.
        """
        return self._get_something_simple(self.at.getInt, Features.AOIHeight)

    @api
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
        self._set_something_simple(self.at.setInt, Features.AOIHeight, value)

    @api
    def getAOILeft(self):
        """Gets the current value of AOILeft.

        Returns
        -------
        int
            The current value of AOILeft.
        """
        return self._get_something_simple(self.at.getInt, Features.AOILeft)

    @api
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
        self._set_something_simple(self.at.setInt, Features.AOILeft, value)

    @api
    def getAOIStride(self):
        """Gets the current value of AOIStride.

        Returns
        -------
        int
            The current value of AOIStride.
        """
        return self._get_something_simple(self.at.getInt, Features.AOIStride)

    @api
    def getAOITop(self):
        """Gets the current value of AOITop.

        Returns
        -------
        int
            The current value of AOITop.
        """
        return self._get_something_simple(self.at.getInt, Features.AOITop)

    @api
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
        self._set_something_simple(self.at.setInt, Features.AOITop, value)

    @api
    def getAOIVBin(self):
        """Gets the current value of AOIVBin.

        Returns
        -------
        int
            The current value of AOIVBin.
        """
        return self._get_something_simple(self.at.getInt, Features.AOIVBin)

    @api
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
        self._set_something_simple(self.at.setInt, Features.AOIVBin, value)

    @api
    def getAOIWidth(self):
        """Gets the current value of AOIWidth.

        Returns
        -------
        int
            The current value of AOIWidth.
        """
        return self._get_something_simple(self.at.getInt, Features.AOIWidth)

    @api
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
        self._set_something_simple(self.at.setInt, Features.AOIWidth, value)

    @api
    def getAuxiliaryOutSource(self):
        """Gets the current value of AuxiliaryOutSource.

        Returns
        -------
        str
            The current value of AuxiliaryOutSource.
        """
        index = self._get_something_simple(
            self.at.getEnumerated, Features.AuxiliaryOutSource
        )
        return self._get_something_with_index(
            self.at.getEnumStringByIndex, Features.AuxiliaryOutSource, index
        )

    @api
    def getAuxiliaryOutSourceValues(self):
        """Gets the possible values of AuxiliaryOutSource.

        Returns
        -------
        str[]
            The possible values of AuxiliaryOutSource.
        """
        count = self._get_something_simple(
            self.at.getEnumCount, Features.AuxiliaryOutSource
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.getEnumStringByIndex, Features.AuxiliaryOutSource, i
                )
            )
        return values

    @api
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
        self._set_something_simple(
            self.at.setEnumeratedString, Features.AuxiliaryOutSource, value
        )

    @api
    def getAuxOutSourceTwo(self):
        """Gets the current value of AuxOutSourceTwo.

        Returns
        -------
        str
            The current value of AuxOutSourceTwo.
        """
        index = self._get_something_simple(
            self.at.getEnumerated, Features.AuxOutSourceTwo
        )
        return self._get_something_with_index(
            self.at.getEnumStringByIndex, Features.AuxOutSourceTwo, index
        )

    @api
    def getAuxOutSourceTwoValues(self):
        """Gets the possible values of AuxOutSourceTwo.

        Returns
        -------
        str[]
            The possible values of AuxOutSourceTwo.
        """
        count = self._get_something_simple(self.at.getEnumCount, Features.AuxOutSourceTwo)
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.getEnumStringByIndex, Features.AuxOutSourceTwo, i
                )
            )
        return values

    @api
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
        self._set_something_simple(
            self.at.setEnumeratedString, Features.AuxOutSourceTwo, value
        )

    @api
    def getBaseline(self):
        """Gets the current value of Baseline.

        Returns
        -------
        int
            The current value of Baseline.
        """
        return self._get_something_simple(self.at.getInt, Features.Baseline)

    @api
    def getBitDepth(self):
        """Gets the current value of BitDepth.

        Returns
        -------
        str
            The current value of BitDepth.
        """
        index = self._get_something_simple(self.at.getEnumerated, Features.BitDepth)
        return self._get_something_with_index(
            self.at.getEnumStringByIndex, Features.BitDepth, index
        )

    @api
    def getBitDepthValues(self):
        """Gets the possible values of BitDepth.

        Returns
        -------
        str[]
            The possible values of BitDepth.
        """
        count = self._get_something_simple(self.at.getEnumCount, Features.BitDepth)
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.getEnumStringByIndex, Features.BitDepth, i
                )
            )
        return values

    @api
    def getBytesPerPixel(self):
        """Gets the current value of BytesPerPixel.

        Returns
        -------
        float
            The current value of BytesPerPixel.
        """
        return self._get_something_simple(self.at.getFloat, Features.BytesPerPixel)

    @api
    def getCameraAcquiring(self):
        """Gets the current value of CameraAcquiring.

        Returns
        -------
        bool
            The current value of CameraAcquiring.
        """
        return self._get_something_simple(self.at.getBool, Features.CameraAcquiring)

    @api
    def getCameraModel(self):
        """Gets the current value of CameraModel.

        Returns
        -------
        str
            The current value of CameraModel.
        """
        return self._get_something_simple(self.at.getString, Features.CameraModel)

    @api
    def getCameraName(self):
        """Gets the current value of CameraName.

        Returns
        -------
        str
            The current value of CameraName.
        """
        return self._get_something_simple(self.at.getString, Features.CameraName)

    @api
    def getCameraPresent(self):
        """Gets the current value of CameraPresent.

        Returns
        -------
        bool
            The current value of CameraPresent.
        """
        return self._get_something_simple(self.at.getBool, Features.CameraPresent)

    @api
    def getControllerID(self):
        """Gets the current value of ControllerID.

        Returns
        -------
        str
            The current value of ControllerID.
        """
        return self._get_something_simple(self.at.getString, Features.ControllerID)

    @api
    def getFrameCount(self):
        """Gets the current value of FrameCount.

        Returns
        -------
        int
            The current value of FrameCount.
        """
        return self._get_something_simple(self.at.getInt, Features.FrameCount)

    @api
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
        self._set_something_simple(self.at.setInt, Features.FrameCount, value)

    @api
    def getCycleMode(self):
        """Gets the current value of CycleMode.

        Returns
        -------
        str
            The current value of CycleMode.
        """
        index = self._get_something_simple(self.at.getEnumerated, Features.CycleMode)
        return self._get_something_with_index(
            self.at.getEnumStringByIndex, Features.CycleMode, index
        )

    @api
    def getCycleModeValues(self):
        """Gets the possible values of CycleMode.

        Returns
        -------
        str[]
            The possible values of CycleMode.
        """
        count = self._get_something_simple(self.at.getEnumCount, Features.CycleMode)
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.getEnumStringByIndex, Features.CycleMode, i
                )
            )
        return values

    @api
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
        self._set_something_simple(self.at.setEnumeratedString, Features.CycleMode, value)

    @api
    def getElectronicShutteringMode(self):
        """Gets the current value of ElectronicShutteringMode.

        Returns
        -------
        str
            The current value of ElectronicShutteringMode.
        """
        index = self._get_something_simple(
            self.at.getEnumerated, Features.ElectronicShutteringMode
        )
        return self._get_something_with_index(
            self.at.getEnumStringByIndex, Features.ElectronicShutteringMode, index
        )

    @api
    def getElectronicShutteringModeValues(self):
        """Gets the possible values of ElectronicShutteringMode.

        Returns
        -------
        str[]
            The possible values of ElectronicShutteringMode.
        """
        count = self._get_something_simple(
            self.at.getEnumCount, Features.ElectronicShutteringMode
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.getEnumStringByIndex, Features.ElectronicShutteringMode, i
                )
            )
        return values

    @api
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
        self._set_something_simple(
            self.at.setEnumeratedString, Features.ElectronicShutteringMode, value
        )

    @api
    def getExposedPixelHeight(self):
        """Gets the current value of ExposedPixelHeight.

        Returns
        -------
        int
            The current value of ExposedPixelHeight.
        """
        return self._get_something_simple(self.at.getInt, Features.ExposedPixelHeight)

    @api
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
        self._set_something_simple(self.at.setInt, Features.ExposedPixelHeight, value)

    @api
    def getExposureTime(self):
        """Gets the current value of ExposureTime.

        Returns
        -------
        float
            The current value of ExposureTime.
        """
        return self._get_something_simple(self.at.getFloat, Features.ExposureTime)

    @api
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
        self._set_something_simple(self.at.setFloat, Features.ExposureTime, value)

    @api
    def getExternalTriggerDelay(self):
        """Gets the current value of ExternalTriggerDelay.

        Returns
        -------
        float
            The current value of ExternalTriggerDelay.
        """
        return self._get_something_simple(self.at.getFloat, Features.ExternalTriggerDelay)

    @api
    def getFanSpeed(self):
        """Gets the current value of FanSpeed.

        Returns
        -------
        str
            The current value of FanSpeed.
        """
        index = self._get_something_simple(self.at.getEnumerated, Features.FanSpeed)
        return self._get_something_with_index(
            self.at.getEnumStringByIndex, Features.FanSpeed, index
        )

    @api
    def getFanSpeedValues(self):
        """Gets the possible values of FanSpeed.

        Returns
        -------
        str[]
            The possible values of FanSpeed.
        """
        count = self._get_something_simple(self.at.getEnumCount, Features.FanSpeed)
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.getEnumStringByIndex, Features.FanSpeed, i
                )
            )
        return values

    @api
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
        self._set_something_simple(self.at.setEnumeratedString, Features.FanSpeed, value)

    @api
    def getFirmwareVersion(self):
        """Gets the current value of FirmwareVersion.

        Returns
        -------
        str
            The current value of FirmwareVersion.
        """
        return self._get_something_simple(self.at.getString, Features.FirmwareVersion)

    @api
    def getFrameRate(self):
        """Gets the current value of FrameRate.

        Returns
        -------
        float
            The current value of FrameRate.
        """
        return self._get_something_simple(self.at.getFloat, Features.FrameRate)

    @api
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
        self._set_something_simple(self.at.setFloat, Features.FrameRate, value)

    @api
    def getFullAOIControl(self):
        """Gets the current value of FullAOIControl.

        Returns
        -------
        bool
            The current value of FullAOIControl.
        """
        return self._get_something_simple(self.at.getBool, Features.FullAOIControl)

    @api
    def getImageSizeBytes(self):
        """Gets the current value of ImageSizeBytes.

        Returns
        -------
        int
            The current value of ImageSizeBytes.
        """
        return self._get_something_simple(self.at.getInt, Features.ImageSizeBytes)

    @api
    def getInterfaceType(self):
        """Gets the current value of InterfaceType.

        Returns
        -------
        str
            The current value of InterfaceType.
        """
        return self._get_something_simple(self.at.getString, Features.InterfaceType)

    @api
    def getIOInvert(self):
        """Gets the current value of IOInvert.

        Returns
        -------
        bool
            The current value of IOInvert.
        """
        return self._get_something_simple(self.at.getBool, Features.IOInvert)

    @api
    def setIOInvert(self, value):
        """Sets IOInvert to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to IOInvert.
        """
        self._set_something_simple(self.at.setBool, Features.IOInvert, value)

    @api
    def getIOSelector(self):
        """Gets the current value of IOSelector.

        Returns
        -------
        str
            The current value of IOSelector.
        """
        index = self._get_something_simple(self.at.getEnumerated, Features.IOSelector)
        return self._get_something_with_index(
            self.at.getEnumStringByIndex, Features.IOSelector, index
        )

    @api
    def getIOSelectorValues(self):
        """Gets the possible values of IOSelector.

        Returns
        -------
        str[]
            The possible values of IOSelector.
        """
        count = self._get_something_simple(self.at.getEnumCount, Features.IOSelector)
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.getEnumStringByIndex, Features.IOSelector, i
                )
            )
        return values

    @api
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
        self._set_something_simple(
            self.at.setEnumeratedString, Features.IOSelector, value
        )

    @api
    def getLineScanSpeed(self):
        """Gets the current value of LineScanSpeed.

        Returns
        -------
        float
            The current value of LineScanSpeed.
        """
        return self._get_something_simple(self.at.getFloat, Features.LineScanSpeed)

    @api
    def getMaxInterfaceTransferRate(self):
        """Gets the current value of MaxInterfaceTransferRate.

        Returns
        -------
        float
            The current value of MaxInterfaceTransferRate.
        """
        return self._get_something_simple(
            self.at.getFloat, Features.MaxInterfaceTransferRate
        )

    @api
    def getMetadataEnable(self):
        """Gets the current value of MetadataEnable.

        Returns
        -------
        bool
            The current value of MetadataEnable.
        """
        return self._get_something_simple(self.at.getBool, Features.MetadataEnable)

    @api
    def setMetadataEnable(self, value):
        """Sets MetadataEnable to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to MetadataEnable.
        """
        self._set_something_simple(self.at.setBool, Features.MetadataEnable, value)

    @api
    def getMetadataTimestamp(self):
        """Gets the current value of MetadataTimestamp.

        Returns
        -------
        bool
            The current value of MetadataTimestamp.
        """
        return self._get_something_simple(self.at.getBool, Features.MetadataTimestamp)

    @api
    def setMetadataTimestamp(self, value):
        """Sets MetadataTimestamp to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to MetadataTimestamp.
        """
        self._set_something_simple(self.at.setBool, Features.MetadataTimestamp, value)

    @api
    def getMetadataFrame(self):
        """Gets the current value of MetadataFrame.

        Returns
        -------
        bool
            The current value of MetadataFrame.
        """
        return self._get_something_simple(self.at.getBool, Features.MetadataFrame)

    @api
    def getOverlap(self):
        """Gets the current value of Overlap.

        Returns
        -------
        bool
            The current value of Overlap.
        """
        return self._get_something_simple(self.at.getBool, Features.Overlap)

    @api
    def setOverlap(self, value):
        """Sets Overlap to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to Overlap.
        """
        self._set_something_simple(self.at.setBool, Features.Overlap, value)

    @api
    def getPixelEncoding(self):
        """Gets the current value of PixelEncoding.

        Returns
        -------
        str
            The current value of PixelEncoding.
        """
        index = self._get_something_simple(self.at.getEnumerated, Features.PixelEncoding)
        return self._get_something_with_index(
            self.at.getEnumStringByIndex, Features.PixelEncoding, index
        )

    @api
    def getPixelEncodingValues(self):
        """Gets the possible values of PixelEncoding.

        Returns
        -------
        str[]
            The possible values of PixelEncoding.
        """
        count = self._get_something_simple(self.at.getEnumCount, Features.PixelEncoding)
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.getEnumStringByIndex, Features.PixelEncoding, i
                )
            )
        return values

    @api
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
        self._set_something_simple(
            self.at.setEnumeratedString, Features.PixelEncoding, value
        )

    @api
    def getPixelHeight(self):
        """Gets the current value of PixelHeight.

        Returns
        -------
        float
            The current value of PixelHeight.
        """
        return self._get_something_simple(self.at.getFloat, Features.PixelHeight)

    @api
    def getPixelReadoutRate(self):
        """Gets the current value of PixelReadoutRate.

        Returns
        -------
        str
            The current value of PixelReadoutRate.
        """
        index = self._get_something_simple(
            self.at.getEnumerated, Features.PixelReadoutRate
        )
        return self._get_something_with_index(
            self.at.getEnumStringByIndex, Features.PixelReadoutRate, index
        )

    @api
    def getPixelReadoutRateValues(self):
        """Gets the possible values of PixelReadoutRate.

        Returns
        -------
        str[]
            The possible values of PixelReadoutRate.
        """
        count = self._get_something_simple(
            self.at.getEnumCount, Features.PixelReadoutRate
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.getEnumStringByIndex, Features.PixelReadoutRate, i
                )
            )
        return values

    @api
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
        self._set_something_simple(
            self.at.setEnumeratedString, Features.PixelReadoutRate, value
        )

    @api
    def getPixelWidth(self):
        """Gets the current value of PixelWidth.

        Returns
        -------
        float
            The current value of PixelWidth.
        """
        return self._get_something_simple(self.at.getFloat, Features.PixelWidth)

    @api
    def getReadoutTime(self):
        """Gets the current value of ReadoutTime.

        Returns
        -------
        float
            The current value of ReadoutTime.
        """
        return self._get_something_simple(self.at.getFloat, Features.ReadoutTime)

    @api
    def getRowReadTime(self):
        """Gets the current value of RowReadTime.

        Returns
        -------
        float
            The current value of RowReadTime.
        """
        return self._get_something_simple(self.at.getFloat, Features.RowReadTime)

    @api
    def getSensorCooling(self):
        """Gets the current value of SensorCooling.

        Returns
        -------
        bool
            The current value of SensorCooling.
        """
        return self._get_something_simple(self.at.getBool, Features.SensorCooling)

    def setSensorCooling(self, value):
        """Sets SensorCooling to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to SensorCooling.
        """
        self._set_something_simple(self.at.setBool, Features.SensorCooling, value)

    @api
    def getSensorHeight(self):
        """Gets the current value of SensorHeight.

        Returns
        -------
        int
            The current value of SensorHeight.
        """
        return self._get_something_simple(self.at.getInt, Features.SensorHeight)

    @api
    def getSensorTemperature(self):
        """Gets the current value of SensorTemperature.

        Returns
        -------
        float
            The current value of SensorTemperature.
        """
        return self._get_something_simple(self.at.getFloat, Features.SensorTemperature)

    @api
    def getSensorWidth(self):
        """Gets the current value of SensorWidth.

        Returns
        -------
        int
            The current value of SensorWidth.
        """
        return self._get_something_simple(self.at.getInt, Features.SensorWidth)

    @api
    def getSerialNumber(self):
        """Gets the current value of SerialNumber.

        Returns
        -------
        str
            The current value of SerialNumber.
        """
        return self._get_something_simple(self.at.getString, Features.SerialNumber)

    @api
    def getShutterOutputMode(self):
        """Gets the current value of ShutterOutputMode.

        Returns
        -------
        str
            The current value of ShutterOutputMode.
        """
        index = self._get_something_simple(
            self.at.getEnumerated, Features.ShutterOutputMode
        )
        return self._get_something_with_index(
            self.at.getEnumStringByIndex, Features.ShutterOutputMode, index
        )

    @api
    def getShutterOutputModeValues(self):
        """Gets the possible values of ShutterOutputMode.

        Returns
        -------
        str[]
            The possible values of ShutterOutputMode.
        """
        count = self._get_something_simple(
            self.at.getEnumCount, Features.ShutterOutputMode
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.getEnumStringByIndex, Features.ShutterOutputMode, i
                )
            )
        return values

    @api
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
        self._set_something_simple(
            self.at.setEnumeratedString, Features.ShutterOutputMode, value
        )

    @api
    def getSimplePreAmpGainControl(self):
        """Gets the current value of SimplePreAmpGainControl.

        Returns
        -------
        str
            The current value of SimplePreAmpGainControl.
        """
        index = self._get_something_simple(
            self.at.getEnumerated, Features.SimplePreAmpGainControl
        )
        return self._get_something_with_index(
            self.at.getEnumStringByIndex, Features.SimplePreAmpGainControl, index
        )

    @api
    def getSimplePreAmpGainControlValues(self):
        """Gets the possible values of SimplePreAmpGainControl.

        Returns
        -------
        str[]
            The possible values of SimplePreAmpGainControl.
        """
        count = self._get_something_simple(
            self.at.getEnumCount, Features.SimplePreAmpGainControl
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.getEnumStringByIndex, Features.SimplePreAmpGainControl, i
                )
            )
        return values

    @api
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
        self._set_something_simple(
            self.at.setEnumeratedString, Features.SimplePreAmpGainControl, value
        )

    @api
    def getShutterTransferTime(self):
        """Gets the current value of ShutterTransferTime.

        Returns
        -------
        float
            The current value of ShutterTransferTime.
        """
        return self._get_something_simple(self.at.getFloat, Features.ShutterTransferTime)

    @api
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
        self._set_something_simple(self.at.setFloat, Features.ShutterTransferTime, value)

    @api
    def cmdSoftwareTrigger(self):
        """Send the SoftwareTrigger command."""
        self._send_command(Features.SoftwareTrigger)

    @api
    def getStaticBlemishCorrection(self):
        """Gets the current value of StaticBlemishCorrection.

        Returns
        -------
        bool
            The current value of StaticBlemishCorrection.
        """
        return self._get_something_simple(
            self.at.getBool, Features.StaticBlemishCorrection
        )

    @api
    def setStaticBlemishCorrection(self, value):
        """Sets StaticBlemishCorrection to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to StaticBlemishCorrection.
        """
        self._set_something_simple(
            self.at.setBool, Features.StaticBlemishCorrection, value
        )

    @api
    def getSpuriousNoiseFilter(self):
        """Gets the current value of SpuriousNoiseFilter.

        Returns
        -------
        bool
            The current value of SpuriousNoiseFilter.
        """
        return self._get_something_simple(self.at.getBool, Features.SpuriousNoiseFilter)

    @api
    def setSpuriousNoiseFilter(self, value):
        """Sets SpuriousNoiseFilter to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to SpuriousNoiseFilter.
        """
        self._set_something_simple(self.at.setBool, Features.SpuriousNoiseFilter, value)

    @api
    def getTargetSensorTemperature(self):
        """Gets the current value of TargetSensorTemperature.

        Returns
        -------
        float
            The current value of TargetSensorTemperature.
        """
        return self._get_something_simple(
            self.at.getFloat, Features.TargetSensorTemperature
        )

    @api
    def getTemperatureControl(self):
        """Gets the current value of TemperatureControl.

        Returns
        -------
        str
            The current value of TemperatureControl.
        """
        index = self._get_something_simple(
            self.at.getEnumerated, Features.TemperatureControl
        )
        return self._get_something_with_index(
            self.at.getEnumStringByIndex, Features.TemperatureControl, index
        )

    @api
    def getTemperatureControlValues(self):
        """Gets the possible values of TemperatureControl.

        Returns
        -------
        str[]
            The possible values of TemperatureControl.
        """
        count = self._get_something_simple(
            self.at.getEnumCount, Features.TemperatureControl
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.getEnumStringByIndex, Features.TemperatureControl, i
                )
            )
        return values

    @api
    def getTemperatureStatus(self):
        """Gets the current value of TemperatureStatus.

        Returns
        -------
        str
            The current value of TemperatureStatus.
        """
        index = self._get_something_simple(
            self.at.getEnumerated, Features.TemperatureStatus
        )
        return self._get_something_with_index(
            self.at.getEnumStringByIndex, Features.TemperatureStatus, index
        )

    @api
    def getTemperatureStatusValues(self):
        """Gets the possible values of TemperatureStatus.

        Returns
        -------
        str[]
            The possible values of TemperatureStatus.
        """
        count = self._get_something_simple(
            self.at.getEnumCount, Features.TemperatureStatus
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.getEnumStringByIndex, Features.TemperatureStatus, i
                )
            )
        return values

    @api
    def getTimestampClock(self):
        """Gets the current value of TimestampClock.

        Returns
        -------
        int
            The current value of TimestampClock.
        """
        return self._get_something_simple(self.at.getInt, Features.TimestampClock)

    @api
    def getTimestampClockFrequency(self):
        """Gets the current value of TimestampClockFrequency.

        Returns
        -------
        int
            The current value of TimestampClockFrequency.
        """
        return self._get_something_simple(
            self.at.getInt, Features.TimestampClockFrequency
        )

    @api
    def getTriggerMode(self):
        """Gets the current value of TriggerMode.

        Returns
        -------
        str
            The current value of TriggerMode.
        """
        index = self._get_something_simple(self.at.getEnumerated, Features.TriggerMode)
        return self._get_something_with_index(
            self.at.getEnumStringByIndex, Features.TriggerMode, index
        )

    @api
    def getTriggerModeValues(self):
        """Gets the possible values of TriggerMode.

        Returns
        -------
        str[]
            The possible values of TriggerMode.
        """
        count = self._get_something_simple(self.at.getEnumCount, Features.TriggerMode)
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.getEnumStringByIndex, Features.TriggerMode, i
                )
            )
        return values

    @api
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
        self._set_something_simple(
            self.at.setEnumeratedString, Features.TriggerMode, value
        )

    @api
    def getVerticallyCentreAOI(self):
        """Gets the current value of VerticallyCentreAOI.

        Returns
        -------
        bool
            The current value of VerticallyCentreAOI.
        """
        return self._get_something_simple(self.at.getBool, Features.VerticallyCentreAOI)

    @api
    def setVerticallyCentreAOI(self, value):
        """Sets VerticallyCentreAOI to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to VerticallyCentreAOI.
        """
        self._set_something_simple(self.at.setBool, Features.VerticallyCentreAOI, value)

    @api
    def queueBuffer(self):
        """Adds a data buffer to the internal driver queue.

        Returns
        -------
        ctypes.c_char_p
            The buffer added to the queue.
        """
        self._assert_handle()
        result, buffer = self.at.queueBuffer(self.handle, self.getImageSizeBytes())
        self._raise_if_bad(result)
        return buffer

    @api
    def waitBuffer(self, buffer, timeout=60000):
        """Waits for a data buffer to be populated during image acquisition.

        Parameters
        ----------
        buffer : ctypes.c_char_p
            The buffer that has already been added to the queue.
        timeout : int
            The timeout.

        Returns
        -------
        int
            The number of bytes populated in the buffer."""
        self._assert_handle()
        result, bytesPopulated = self.at.waitBuffer(self.handle, buffer, timeout)
        self._raise_if_bad(result)
        return bytesPopulated

    def flush(self):
        """Flushes the current data buffer queue."""
        self._assert_handle()
        result = self.at.flush(self.handle)
        self._raise_if_bad(result)

    def take(self, frame_count):
        self.flush()
        self.setFrameCount(frame_count)
        buffers = []
        for i in range(frame_count):
            buffers.append(self.queueBuffer())
        self.cmdAcquisitionStart()
        for buffer in buffers:
            self.waitBuffer(buffer)
        return buffers

    def take_one(self):
        self.flush()
        buffer = self.queueBuffer()
        self.cmdAcquisitionStart()
        self.waitBuffer(buffer)
        return buffer

    def _set_something_simple(self, action, feature, value):
        self._assert_handle()
        result = action(self.handle, feature, value)
        self._raise_if_bad(result)

    def _get_something_simple(self, action, feature):
        self._assert_handle()
        result, something = action(self.handle, feature)
        self._raise_if_bad(result)
        return something

    def _get_something_with_index(self, action, feature, index):
        self._assert_handle()
        result, something = action(self.handle, feature, index)
        self._raise_if_bad(result)
        return something

    def _send_command(self, feature):
        self._assert_handle()
        result = self.at.command(self.handle, feature)
        self._raise_if_bad(result)

    def _assert_handle(self):
        if self.handle == -1:
            raise ATDeviceNotOpenError()
