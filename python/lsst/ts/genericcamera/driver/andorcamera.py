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
import enum
import struct
from ctypes.util import find_library

import numpy as np
import yaml

from ..exposure import Exposure
from .basecamera import BaseCamera


class AndorCamera(BaseCamera):
    def __init__(self, log=None):
        super().__init__(log)
        self.lib = ATLibrary()
        self.lib.initialise_library()
        self.is_live_exposure = False
        self.id = 0
        self.accumulate_count = 1
        self.bin_value = 1
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
        self.bin_value = 1
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
        return self.dev.get_camera_model() + " " + self.dev.get_camera_name()

    def set_ROI(self, top, left, width, height):
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
        self.dev.set_AOI_top(top)
        self.dev.set_AOI_left(left)
        self.dev.set_AOI_width(width)
        self.dev.set_AOI_height(height)

    def get_ROI(self):
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
        top = self.dev.get_AOI_top()
        left = self.dev.get_AOI_left()
        width = self.dev.get_AOI_width()
        height = self.dev.get_AOI_height()
        return top, left, width, height

    def set_full_frame(self):
        """Sets the region of interest to the whole sensor."""
        result, width = self.dev.at.get_int_max(self.dev.handle, Features.AOIWidth)
        result, height = self.dev.at.get_int_max(self.dev.handle, Features.AOIHeight)
        self.set_ROI(0, 0, width, height)

    def set_exposure_time(self, duration):
        """Sets the exposure time.

        Parameters
        ----------
        duration : float
            The exposure time in seconds."""
        self.dev.set_exposure_time(duration)

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
        buffer = self.dev.queue_buffer()
        self.dev.cmd_acquisition_start()
        bytes_received = 0
        while bytes_received == 0:
            try:
                bytes_received = self.dev.wait_buffer(buffer, 0)
                await asyncio.sleep(0.02)
            except ATError as e:
                if e.result != Results.TimedOut:
                    raise e
        top = self.dev.get_AOI_top()
        left = self.dev.get_AOI_left()
        width = self.dev.get_AOI_width()
        height = self.dev.get_AOI_height()
        exposure = self.dev.get_exposure_time()
        temperature = self.dev.get_sensor_temperature()
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

    def initialise_library(self):
        # int AT_EXP_CONV AT_InitialiseLibrary();
        return self._to_result_enum(self.lib.AT_InitialiseLibrary())

    def finalise_library(self):
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

    def is_implemented(self, handle, feature):
        # int AT_EXP_CONV AT_IsImplemented(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* Implemented);
        implemented = self._get_bool_ptr()
        result = self.lib.AT_IsImplemented(handle, feature.name, implemented)
        return self._to_result_enum(result), implemented[0]

    def is_readable(self, handle, feature):
        # int AT_EXP_CONV AT_IsReadable(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* Readable);
        readable = self._get_bool_ptr()
        result = self.lib.AT_IsReadable(handle, feature.name, readable)
        return self._to_result_enum(result), readable[0]

    def is_writable(self, handle, feature):
        # int AT_EXP_CONV AT_IsWritable(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* Writable);
        writable = self._get_bool_ptr()
        result = self.lib.AT_IsWritable(handle, feature.name, writable)
        return self._to_result_enum(result), writable[0]

    def is_read_only(self, handle, feature):
        # int AT_EXP_CONV AT_IsReadOnly(AT_H Hndl, const AT_WC* Feature,
        # AT_BOOL* ReadOnly);
        read_only = self._get_bool_ptr()
        result = self.lib.AT_IsReadOnly(handle, feature.name, read_only)
        return self._to_result_enum(result), read_only[0]

    def set_int(self, handle, feature, value):
        # int AT_EXP_CONV AT_SetInt(AT_H Hndl, const AT_WC* Feature, AT_64
        # Value);
        return self._to_result_enum(self.lib.AT_SetInt(handle, feature.name, value))

    def get_int(self, handle, feature):
        # int AT_EXP_CONV AT_GetInt(AT_H Hndl, const AT_WC* Feature, AT_64*
        # Value);
        value = self._get_long_long_ptr()
        result = self.lib.AT_GetInt(handle, feature.name, value)
        return self._to_result_enum(result), value[0]

    def get_int_max(self, handle, feature):
        # int AT_EXP_CONV AT_GetIntMax(AT_H Hndl, const AT_WC* Feature, AT_64*
        # MaxValue);
        max_value = self._get_long_long_ptr()
        result = self.lib.AT_GetIntMax(handle, feature.name, max_value)
        return self._to_result_enum(result), max_value[0]

    def get_int_min(self, handle, feature):
        # int AT_EXP_CONV AT_GetIntMin(AT_H Hndl, const AT_WC* Feature, AT_64*
        # MinValue);
        min_value = self._get_long_long_ptr()
        result = self.lib.AT_GetIntMin(handle, feature.name, min_value)
        return self._to_result_enum(result), min_value[0]

    def set_float(self, handle, feature, value):
        # int AT_EXP_CONV AT_SetFloat(AT_H Hndl, const AT_WC* Feature, double
        # Value);
        return self._to_result_enum(self.lib.AT_SetFloat(handle, feature.name, value))

    def get_float(self, handle, feature):
        # int AT_EXP_CONV AT_GetFloat(AT_H Hndl, const AT_WC* Feature, double*
        # Value);
        value = self._get_double_ptr()
        result = self.lib.AT_GetFloat(handle, feature.name, value)
        return self._to_result_enum(result), value[0]

    def get_float_max(self, handle, feature):
        # int AT_EXP_CONV AT_GetFloatMax(AT_H Hndl, const AT_WC* Feature,
        # double* MaxValue);
        max_value = self._get_double_ptr()
        result = self.lib.AT_GetFloatMax(handle, feature.name, max_value)
        return self._to_result_enum(result), max_value[0]

    def get_float_min(self, handle, feature):
        # int AT_EXP_CONV AT_GetFloatMin(AT_H Hndl, const AT_WC* Feature,
        # double* MinValue);
        min_value = self._get_double_ptr()
        result = self.lib.AT_GetFloatMin(handle, feature.name, min_value)
        return self._to_result_enum(result), min_value[0]

    def set_bool(self, handle, feature, value):
        # int AT_EXP_CONV AT_SetBool(AT_H Hndl, const AT_WC* Feature, AT_BOOL
        # Value);
        return self._to_result_enum(self.lib.AT_SetBool(handle, feature.name, value))

    def get_bool(self, handle, feature):
        # int AT_EXP_CONV AT_GetBool(AT_H Hndl, const AT_WC* Feature, AT_BOOL*
        # Value);
        value = self._get_bool_ptr()
        result = self.lib.AT_GetBool(handle, feature.name, value)
        return self._to_result_enum(result), value[0]

    def set_enumerated(self, handle, feature, value):
        # int AT_EXP_CONV AT_SetEnumerated(AT_H Hndl, const AT_WC* Feature, int
        # Value);
        return self._to_result_enum(
            self.lib.AT_SetEnumerated(handle, feature.name, value)
        )

    def set_enumerated_string(self, handle, feature, string):
        # int AT_EXP_CONV AT_SetEnumeratedString(AT_H Hndl,
        # const AT_WC* Feature, const AT_WC* String);
        return self._to_result_enum(
            self.lib.AT_SetEnumeratedString(handle, feature.name, string)
        )

    def get_enumerated(self, handle, feature):
        # int AT_EXP_CONV AT_GetEnumerated(AT_H Hndl, const AT_WC* Feature,
        # int* Value);
        value = self._get_int_ptr()
        result = self.lib.AT_GetEnumerated(handle, feature.name, value)
        return self._to_result_enum(result), value[0]

    def get_enumerated_count(self, handle, feature):
        # int AT_EXP_CONV AT_GetEnumeratedCount(AT_H Hndl,const  AT_WC*
        # Feature, int* Count);
        count = self._get_int_ptr()
        result = self.lib.AT_GetEnumeratedCount(handle, feature.name, count)
        return self._to_result_enum(result), count[0]

    def is_enumerated_index_availabe(self, handle, feature, index):
        # int AT_EXP_CONV AT_IsEnumeratedIndexAvailable(AT_H Hndl,
        # const AT_WC* Feature, int Index, AT_BOOL* Available);
        available = self._get_bool_ptr()
        result = self.lib.AT_IsEnumeratedIndexAvailable(
            handle, feature.name, index, available
        )
        return self._to_result_enum(result), available[0]

    def is_enumerated_index_implemented(self, handle, feature, index):
        # int AT_EXP_CONV AT_IsEnumeratedIndexImplemented(AT_H Hndl,
        #  const AT_WC* Feature, int Index, AT_BOOL* Implemented);
        implemented = self._get_bool_ptr()
        result = self.lib.AT_IsEnumeratedIndexImplemented(
            handle, feature.name, index, implemented
        )
        return self._to_result_enum(result), implemented[0]

    def get_enumerated_string(self, handle, feature, index):
        # int AT_EXP_CONV AT_GetEnumeratedString(AT_H Hndl,
        # const AT_WC* Feature, int Index, AT_WC* String, int StringLength);
        string = self._get_unicode_buffer()
        result = self.lib.AT_GetEnumeratedString(
            handle, feature.name, index, string, len(string)
        )
        return self._to_result_enum(result), string.value

    def set_enum_index(self, handle, feature, value):
        # int AT_EXP_CONV AT_SetEnumIndex(AT_H Hndl, const AT_WC* Feature,
        # int Value);
        return self._to_result_enum(
            self.lib.AT_SetEnumIndex(handle, feature.name, value)
        )

    def set_enum_string(self, handle, feature, string):
        # int AT_EXP_CONV AT_SetEnumString(AT_H Hndl, const AT_WC* Feature,
        # const AT_WC* String);
        return self._to_result_enum(
            self.lib.AT_SetEnumString(handle, feature.name, string)
        )

    def get_enum_index(self, handle, feature):
        # int AT_EXP_CONV AT_GetEnumIndex(AT_H Hndl, const AT_WC* Feature,
        # int* Value);
        value = self._get_int_ptr()
        result = self.lib.AT_GetEnumIndex(handle, feature.name, value)
        return self._to_result_enum(result), value[0]

    def get_enum_count(self, handle, feature):
        # int AT_EXP_CONV AT_GetEnumCount(AT_H Hndl,const  AT_WC* Feature,
        # int* Count);
        count = self._get_int_ptr()
        result = self.lib.AT_GetEnumCount(handle, feature.name, count)
        return self._to_result_enum(result), count[0]

    def is_enum_index_available(self, handle, feature, index):
        # int AT_EXP_CONV AT_IsEnumIndexAvailable(AT_H Hndl,
        # const AT_WC* Feature, int Index, AT_BOOL* Available);
        available = self._get_bool_ptr()
        result = self.lib.AT_IsEnumIndexAvailable(
            handle, feature.name, index, available
        )
        return self._to_result_enum(result), available[0]

    def is_enum_index_implemented(self, handle, feature, index):
        # int AT_EXP_CONV AT_IsEnumIndexImplemented(AT_H Hndl,
        # const AT_WC* Feature, int Index, AT_BOOL* Implemented);
        implemented = self._get_bool_ptr()
        result = self.lib.AT_IsEnumIndexImplemented(
            handle, feature.name, index, implemented
        )
        return self._to_result_enum(result), implemented[0]

    def get_enum_string_by_index(self, handle, feature, index):
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

    def set_string(self, handle, feature, string):
        # int AT_EXP_CONV AT_SetString(AT_H Hndl, const AT_WC* Feature, const
        # AT_WC* String);
        return self._to_result_enum(self.lib.AT_SetString(handle, feature.name, string))

    def get_string(self, handle, feature):
        # int AT_EXP_CONV AT_GetString(AT_H Hndl, const AT_WC* Feature,
        # AT_WC* String, int StringLength);
        string = self._get_unicode_buffer()
        result = self.lib.AT_GetString(handle, feature.name, string, len(string))
        return self._to_result_enum(result), string.value

    def get_string_max_length(self, handle, feature):
        # int AT_EXP_CONV AT_GetStringMaxLength(AT_H Hndl,
        # const AT_WC* Feature, int* MaxStringLength);
        max_string_length = self._get_int_ptr()
        result = self.lib.AT_GetStringMaxLength(handle, feature.name, max_string_length)
        return self._to_result_enum(result), max_string_length[0]

    def queue_buffer(self, handle, buffer_size):
        # int AT_EXP_CONV AT_QueueBuffer(AT_H Hndl, AT_U8* Ptr, int PtrSize);
        buffer = self._get_string_buffer(buffer_size)
        result = self.lib.AT_QueueBuffer(handle, buffer, len(buffer))
        return self._to_result_enum(result), buffer

    def wait_buffer(self, handle, buffer, timeout=60):
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


class ATLibraryNotInitialisedError(Exception):
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

    def initialise_library(self):
        if not self.initialised:
            self.at.initialise_library()
            self.initialised = True

    def finalise_library(self):
        if self.initialised:
            self.at.finalise_library()
            self.initialised = False

    def get_device_count(self):
        if not self.initialised:
            raise ATLibraryNotInitialisedError()
        result, device_count = self.at.get_int(1, Features.DeviceCount)
        self._raise_if_bad(result)
        return device_count

    def open_zyla(self, camera_index):
        if not self.initialised:
            raise ATLibraryNotInitialisedError()
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

    def get_accumulate_count(self):
        """Gets the current value of AccumulateCount.

        Returns
        -------
        int
            The current value of AccumulateCount.
        """
        return self._get_something_simple(self.at.get_int, Features.AccumulateCount)

    def set_accumulatei_count(self, value):
        """Sets AccumulateCount to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to AccumulateCount.
        """
        result, min_value = self.at.get_int_min(self.handle, Features.AccumulateCount)
        result, max_value = self.at.get_int_max(self.handle, Features.AccumulateCount)
        if value < min_value or value > max_value:
            raise ValueError(
                f"Value ({value}) for AccumulateCount must be "
                f"between {min_value} and {max_value}."
            )
        self._set_something_simple(self.at.set_int, Features.AccumulateCount, value)

    def cmd_acquisition_start(self):
        """Send the AcquisitionStart command."""
        self._send_command(Features.AcquisitionStart)

    def cmd_acquisition_stop(self):
        """Send the AcquisitionStop command."""
        self._send_command(Features.AcquisitionStop)

    def get_AOI_binning(self):
        """Gets the current value of AOIBinning.

        Returns
        -------
        str
            The current value of AOIBinning.
        """
        index = self._get_something_simple(self.at.get_enumerated, Features.AOIBinning)
        return self._get_something_with_index(
            self.at.get_enum_string_by_index, Features.AOIBinning, index
        )

    def get_AOI_binning_values(self):
        """Gets the possible values of AOIBinning.

        Returns
        -------
        str[]
            The possible values of AOIBinning.
        """
        count = self._get_something_simple(self.at.get_enum_count, Features.AOIBinning)
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.get_enum_string_by_index, Features.AOIBinning, i
                )
            )
        return values

    def set_AOI_binning(self, value):
        """Sets AOIBinning to the specified value.

        Use get_AOI_binning_values() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to AOIBinning.
        """
        valid_values = self.get_AOI_binning_values()
        if value not in valid_values:
            raise ValueError(
                f"The value {value} is not a valid value for AOIBinning. "
                f"Valid values are {valid_values}."
            )
        self._set_something_simple(
            self.at.set_enumerated_string, Features.AOIBinning, value
        )

    def get_AOI_hbin(self):
        """Gets the current value of AOIHBin.

        Returns
        -------
        int
            The current value of AOIHBin.
        """
        return self._get_something_simple(self.at.get_int, Features.AOIHBin)

    def set_AOI_hbin(self, value):
        """Sets AOIHBin to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to AOIHBin.
        """
        result, min_value = self.at.get_int_min(self.handle, Features.AOIHBin)
        result, max_value = self.at.get_inti_max(self.handle, Features.AOIHBin)
        if value < min_value or value > max_value:
            raise ValueError(
                f"Value ({value}) for AOIHBin must be between "
                f"{min_value} and {max_value}."
            )
        self._set_something_simple(self.at.set_int, Features.AOIHBin, value)

    def get_AOI_height(self):
        """Gets the current value of AOIHeight.

        Returns
        -------
        int
            The current value of AOIHeight.
        """
        return self._get_something_simple(self.at.get_int, Features.AOIHeight)

    def set_AOI_height(self, value):
        """Sets AOIHeight to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to AOIHeight.
        """
        result, min_value = self.at.get_int_min(self.handle, Features.AOIHeight)
        result, max_value = self.at.get_int_max(self.handle, Features.AOIHeight)
        if value < min_value or value > max_value:
            raise ValueError(
                f"Value ({value}) for AOIHeight must be between "
                f"{min_value} and {max_value}."
            )
        self._set_something_simple(self.at.set_int, Features.AOIHeight, value)

    def get_AOI_left(self):
        """Gets the current value of AOILeft.

        Returns
        -------
        int
            The current value of AOILeft.
        """
        return self._get_something_simple(self.at.get_int, Features.AOILeft)

    def set_AOI_left(self, value):
        """Sets AOILeft to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to AOILeft.
        """
        result, min_value = self.at.get_int_min(self.handle, Features.AOILeft)
        result, max_value = self.at.get_int_max(self.handle, Features.AOILeft)
        if value < min_value or value > max_value:
            raise ValueError(
                f"Value ({value}) for AOILeft must be between "
                f"{min_value} and {max_value}."
            )
        self._set_something_simple(self.at.set_int, Features.AOILeft, value)

    def get_AOI_stride(self):
        """Gets the current value of AOIStride.

        Returns
        -------
        int
            The current value of AOIStride.
        """
        return self._get_something_simple(self.at.get_int, Features.AOIStride)

    def get_AOI_top(self):
        """Gets the current value of AOITop.

        Returns
        -------
        int
            The current value of AOITop.
        """
        return self._get_something_simple(self.at.get_int, Features.AOITop)

    def set_AOI_top(self, value):
        """Sets AOITop to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to AOITop.
        """
        result, min_value = self.at.get_int_min(self.handle, Features.AOITop)
        result, max_value = self.at.get_int_max(self.handle, Features.AOITop)
        if value < min_value or value > max_value:
            raise ValueError(
                f"Value ({value}) for AOITop must be between "
                f"{min_value} and {max_value}."
            )
        self._set_something_simple(self.at.set_int, Features.AOITop, value)

    def get_AOI_vbin(self):
        """Gets the current value of AOIVBin.

        Returns
        -------
        int
            The current value of AOIVBin.
        """
        return self._get_something_simple(self.at.get_int, Features.AOIVBin)

    def set_AOI_vbin(self, value):
        """Sets AOIVBin to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to AOIVBin.
        """
        result, min_value = self.at.get_int_min(self.handle, Features.AOIVBin)
        result, max_value = self.at.get_int_max(self.handle, Features.AOIVBin)
        if value < min_value or value > max_value:
            raise ValueError(
                f"Value ({value}) for AOIVBin must be between "
                f"{min_value} and {max_value}."
            )
        self._set_something_simple(self.at.set_int, Features.AOIVBin, value)

    def get_AOI_width(self):
        """Gets the current value of AOIWidth.

        Returns
        -------
        int
            The current value of AOIWidth.
        """
        return self._get_something_simple(self.at.get_int, Features.AOIWidth)

    def set_AOI_width(self, value):
        """Sets AOIWidth to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to AOIWidth.
        """
        result, min_value = self.at.get_int_min(self.handle, Features.AOIWidth)
        result, max_value = self.at.get_int_max(self.handle, Features.AOIWidth)
        if value < min_value or value > max_value:
            raise ValueError(
                f"Value ({value}) for AOIWidth must be between "
                f"{min_value} and {max_value}."
            )
        self._set_something_simple(self.at.set_int, Features.AOIWidth, value)

    def get_auxiliary_out_source(self):
        """Gets the current value of AuxiliaryOutSource.

        Returns
        -------
        str
            The current value of AuxiliaryOutSource.
        """
        index = self._get_something_simple(
            self.at.get_enumerated, Features.AuxiliaryOutSource
        )
        return self._get_something_with_index(
            self.at.get_enum_string_by_index, Features.AuxiliaryOutSource, index
        )

    def get_auxiliary_out_source_values(self):
        """Gets the possible values of AuxiliaryOutSource.

        Returns
        -------
        str[]
            The possible values of AuxiliaryOutSource.
        """
        count = self._get_something_simple(
            self.at.get_enum_count, Features.AuxiliaryOutSource
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.get_enum_string_by_index, Features.AuxiliaryOutSource, i
                )
            )
        return values

    def set_auxiliary_out_source(self, value):
        """Sets AuxiliaryOutSource to the specified value.

        Use get_auxiliary_out_source_values() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to AuxiliaryOutSource.
        """
        valid_values = self.get_auxiliary_out_source_values()
        if value not in valid_values:
            raise ValueError(
                f"The value {value} is not a valid value for "
                f"AuxiliaryOutSource. Valid values are {valid_values}."
            )
        self._set_something_simple(
            self.at.set_enumerated_string, Features.AuxiliaryOutSource, value
        )

    def get_aux_out_source_two(self):
        """Gets the current value of AuxOutSourceTwo.

        Returns
        -------
        str
            The current value of AuxOutSourceTwo.
        """
        index = self._get_something_simple(
            self.at.get_enumerated, Features.AuxOutSourceTwo
        )
        return self._get_something_with_index(
            self.at.get_enum_string_by_index, Features.AuxOutSourceTwo, index
        )

    def get_aux_out_source_two_values(self):
        """Gets the possible values of AuxOutSourceTwo.

        Returns
        -------
        str[]
            The possible values of AuxOutSourceTwo.
        """
        count = self._get_something_simple(
            self.at.get_enum_count, Features.AuxOutSourceTwo
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.get_enum_string_by_index, Features.AuxOutSourceTwo, i
                )
            )
        return values

    def set_aux_out_source_two(self, value):
        """Sets AuxOutSourceTwo to the specified value.

        Use get_aux_out_source_two_values() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to AuxOutSourceTwo.
        """
        valid_values = self.get_aux_out_source_two_values()
        if value not in valid_values:
            raise ValueError(
                f"The value {value} is not a valid value for "
                f"AuxOutSourceTwo. Valid values are {valid_values}."
            )
        self._set_something_simple(
            self.at.set_enumerated_string, Features.AuxOutSourceTwo, value
        )

    def get_baseline(self):
        """Gets the current value of Baseline.

        Returns
        -------
        int
            The current value of Baseline.
        """
        return self._get_something_simple(self.at.get_int, Features.Baseline)

    def get_bit_depth(self):
        """Gets the current value of BitDepth.

        Returns
        -------
        str
            The current value of BitDepth.
        """
        index = self._get_something_simple(self.at.get_enumerated, Features.BitDepth)
        return self._get_something_with_index(
            self.at.get_enum_string_by_index, Features.BitDepth, index
        )

    def get_bit_depth_values(self):
        """Gets the possible values of BitDepth.

        Returns
        -------
        str[]
            The possible values of BitDepth.
        """
        count = self._get_something_simple(self.at.get_enum_count, Features.BitDepth)
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.get_enum_string_by_index, Features.BitDepth, i
                )
            )
        return values

    def get_bytes_per_pixel(self):
        """Gets the current value of BytesPerPixel.

        Returns
        -------
        float
            The current value of BytesPerPixel.
        """
        return self._get_something_simple(self.at.get_float, Features.BytesPerPixel)

    def get_camera_acquiring(self):
        """Gets the current value of CameraAcquiring.

        Returns
        -------
        bool
            The current value of CameraAcquiring.
        """
        return self._get_something_simple(self.at.get_bool, Features.CameraAcquiring)

    def get_camera_model(self):
        """Gets the current value of CameraModel.

        Returns
        -------
        str
            The current value of CameraModel.
        """
        return self._get_something_simple(self.at.get_string, Features.CameraModel)

    def get_camera_name(self):
        """Gets the current value of CameraName.

        Returns
        -------
        str
            The current value of CameraName.
        """
        return self._get_something_simple(self.at.get_string, Features.CameraName)

    def get_camera_present(self):
        """Gets the current value of CameraPresent.

        Returns
        -------
        bool
            The current value of CameraPresent.
        """
        return self._get_something_simple(self.at.get_bool, Features.CameraPresent)

    def get_controller_ID(self):
        """Gets the current value of ControllerID.

        Returns
        -------
        str
            The current value of ControllerID.
        """
        return self._get_something_simple(self.at.get_string, Features.ControllerID)

    def get_frame_count(self):
        """Gets the current value of FrameCount.

        Returns
        -------
        int
            The current value of FrameCount.
        """
        return self._get_something_simple(self.at.get_int, Features.FrameCount)

    def set_frame_count(self, value):
        """Sets FrameCount to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to FrameCount.
        """
        result, min_value = self.at.get_int_min(self.handle, Features.FrameCount)
        result, max_value = self.at.get_int_max(self.handle, Features.FrameCount)
        if value < min_value or value > max_value:
            raise ValueError(
                f"Value ({value}) for FrameCount must be between "
                f"{min_value} and {max_value}."
            )
        self._set_something_simple(self.at.set_int, Features.FrameCount, value)

    def get_cycle_mode(self):
        """Gets the current value of CycleMode.

        Returns
        -------
        str
            The current value of CycleMode.
        """
        index = self._get_something_simple(self.at.get_enumerated, Features.CycleMode)
        return self._get_something_with_index(
            self.at.get_enum_string_by_index, Features.CycleMode, index
        )

    def get_cycle_mode_values(self):
        """Gets the possible values of CycleMode.

        Returns
        -------
        str[]
            The possible values of CycleMode.
        """
        count = self._get_something_simple(self.at.get_enum_count, Features.CycleMode)
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.get_enum_string_by_index, Features.CycleMode, i
                )
            )
        return values

    def set_cycle_mode(self, value):
        """Sets CycleMode to the specified value.

        Use get_cycle_mode_values() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to CycleMode.
        """
        valid_values = self.get_cycle_mode_values()
        if value not in valid_values:
            raise ValueError(
                f"The value {value} is not a valid value for CycleMode. "
                f"Valid values are {valid_values}."
            )
        self._set_something_simple(
            self.at.set_enumerated_string, Features.CycleMode, value
        )

    def get_electronic_shuttering_mode(self):
        """Gets the current value of ElectronicShutteringMode.

        Returns
        -------
        str
            The current value of ElectronicShutteringMode.
        """
        index = self._get_something_simple(
            self.at.get_enumerated, Features.ElectronicShutteringMode
        )
        return self._get_something_with_index(
            self.at.get_enum_string_by_index, Features.ElectronicShutteringMode, index
        )

    def get_electronic_shuttering_mode_values(self):
        """Gets the possible values of ElectronicShutteringMode.

        Returns
        -------
        str[]
            The possible values of ElectronicShutteringMode.
        """
        count = self._get_something_simple(
            self.at.get_enum_count, Features.ElectronicShutteringMode
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.get_enum_string_by_index,
                    Features.ElectronicShutteringMode,
                    i,
                )
            )
        return values

    def set_electronic_shuttering_mode(self, value):
        """Sets ElectronicShutteringMode to the specified value.

        Use get_electronic_shuttering_mode_values() to get a list of valid
        values.

        Parameters
        ----------
        value : str
            The value to apply to ElectronicShutteringMode.
        """
        valid_values = self.get_electronic_shuttering_mode_values()
        if value not in valid_values:
            raise ValueError(
                f"The value {value} is not a valid value for "
                f"ElectronicShutteringMode. Valid values are {valid_values}."
            )
        self._set_something_simple(
            self.at.set_enumerated_string, Features.ElectronicShutteringMode, value
        )

    def get_exposed_pixel_height(self):
        """Gets the current value of ExposedPixelHeight.

        Returns
        -------
        int
            The current value of ExposedPixelHeight.
        """
        return self._get_something_simple(self.at.get_int, Features.ExposedPixelHeight)

    def set_exposed_pixel_height(self, value):
        """Sets ExposedPixelHeight to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : int
            The value to apply to ExposedPixelHeight.
        """
        result, min_value = self.at.get_int_min(
            self.handle, Features.ExposedPixelHeight
        )
        result, max_value = self.at.get_int_max(
            self.handle, Features.ExposedPixelHeight
        )
        if value < min_value or value > max_value:
            raise ValueError(
                f"Value ({value}) for ExposedPixelHeight must be "
                f"between {min_value} and {max_value}."
            )
        self._set_something_simple(self.at.set_int, Features.ExposedPixelHeight, value)

    def get_exposure_time(self):
        """Gets the current value of ExposureTime.

        Returns
        -------
        float
            The current value of ExposureTime.
        """
        return self._get_something_simple(self.at.get_float, Features.ExposureTime)

    def set_exposure_time(self, value):
        """Sets ExposureTime to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : float
            The value to apply to ExposureTime.
        """
        result, min_value = self.at.get_float_min(self.handle, Features.ExposureTime)
        result, max_value = self.at.get_float_max(self.handle, Features.ExposureTime)
        if value < min_value or value > max_value:
            raise ValueError(
                f"Value ({value}) for ExposureTime must be between "
                f"{min_value} and {max_value}."
            )
        self._set_something_simple(self.at.set_float, Features.ExposureTime, value)

    def get_external_trigger_delay(self):
        """Gets the current value of ExternalTriggerDelay.

        Returns
        -------
        float
            The current value of ExternalTriggerDelay.
        """
        return self._get_something_simple(
            self.at.get_float, Features.ExternalTriggerDelay
        )

    def get_fan_speed(self):
        """Gets the current value of FanSpeed.

        Returns
        -------
        str
            The current value of FanSpeed.
        """
        index = self._get_something_simple(self.at.get_enumerated, Features.FanSpeed)
        return self._get_something_with_index(
            self.at.get_enum_string_by_index, Features.FanSpeed, index
        )

    def get_fan_speed_values(self):
        """Gets the possible values of FanSpeed.

        Returns
        -------
        str[]
            The possible values of FanSpeed.
        """
        count = self._get_something_simple(self.at.get_enum_count, Features.FanSpeed)
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.get_enum_string_by_index, Features.FanSpeed, i
                )
            )
        return values

    def set_fan_speed(self, value):
        """Sets FanSpeed to the specified value.

        Use get_fan_speed_values() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to FanSpeed.
        """
        valid_values = self.get_fan_speed_values()
        if value not in valid_values:
            raise ValueError(
                f"The value {value} is not a valid value for FanSpeed. "
                f"Valid values are {valid_values}."
            )
        self._set_something_simple(
            self.at.set_enumerated_string, Features.FanSpeed, value
        )

    def get_firmware_version(self):
        """Gets the current value of FirmwareVersion.

        Returns
        -------
        str
            The current value of FirmwareVersion.
        """
        return self._get_something_simple(self.at.get_string, Features.FirmwareVersion)

    def get_frame_rate(self):
        """Gets the current value of FrameRate.

        Returns
        -------
        float
            The current value of FrameRate.
        """
        return self._get_something_simple(self.at.get_float, Features.FrameRate)

    def set_frameate(self, value):
        """Sets FrameRate to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : float
            The value to apply to FrameRate.
        """
        result, min_value = self.at.get_float_min(self.handle, Features.FrameRate)
        result, max_value = self.at.get_float_max(self.handle, Features.FrameRate)
        if value < min_value or value > max_value:
            raise ValueError(
                f"Value ({value}) for FrameRate must be between "
                f"{min_value} and {max_value}."
            )
        self._set_something_simple(self.at.set_float, Features.FrameRate, value)

    def get_full_AOI_control(self):
        """Gets the current value of FullAOIControl.

        Returns
        -------
        bool
            The current value of FullAOIControl.
        """
        return self._get_something_simple(self.at.get_bool, Features.FullAOIControl)

    def get_image_size_bytes(self):
        """Gets the current value of ImageSizeBytes.

        Returns
        -------
        int
            The current value of ImageSizeBytes.
        """
        return self._get_something_simple(self.at.get_int, Features.ImageSizeBytes)

    def get_interface_type(self):
        """Gets the current value of InterfaceType.

        Returns
        -------
        str
            The current value of InterfaceType.
        """
        return self._get_something_simple(self.at.get_string, Features.InterfaceType)

    def get_IO_invert(self):
        """Gets the current value of IOInvert.

        Returns
        -------
        bool
            The current value of IOInvert.
        """
        return self._get_something_simple(self.at.get_bool, Features.IOInvert)

    def set_IO_invert(self, value):
        """Sets IOInvert to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to IOInvert.
        """
        self._set_something_simple(self.at.set_bool, Features.IOInvert, value)

    def get_IO_selector(self):
        """Gets the current value of IOSelector.

        Returns
        -------
        str
            The current value of IOSelector.
        """
        index = self._get_something_simple(self.at.get_enumerated, Features.IOSelector)
        return self._get_something_with_index(
            self.at.get_enum_string_by_index, Features.IOSelector, index
        )

    def get_IO_selector_values(self):
        """Gets the possible values of IOSelector.

        Returns
        -------
        str[]
            The possible values of IOSelector.
        """
        count = self._get_something_simple(self.at.get_enum_count, Features.IOSelector)
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.get_enum_string_by_index, Features.IOSelector, i
                )
            )
        return values

    def set_IO_selector(self, value):
        """Sets IOSelector to the specified value.

        Use get_IO_selector_values() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to IOSelector.
        """
        valid_values = self.get_IO_selector_values()
        if value not in valid_values:
            raise ValueError(
                f"The value {value} is not a valid value for IOSelector. "
                f"Valid values are {valid_values}."
            )
        self._set_something_simple(
            self.at.set_enumerated_string, Features.IOSelector, value
        )

    def get_line_scan_speed(self):
        """Gets the current value of LineScanSpeed.

        Returns
        -------
        float
            The current value of LineScanSpeed.
        """
        return self._get_something_simple(self.at.get_float, Features.LineScanSpeed)

    def get_max_interface_transfer_rate(self):
        """Gets the current value of MaxInterfaceTransferRate.

        Returns
        -------
        float
            The current value of MaxInterfaceTransferRate.
        """
        return self._get_something_simple(
            self.at.get_float, Features.MaxInterfaceTransferRate
        )

    def get_metadata_enable(self):
        """Gets the current value of MetadataEnable.

        Returns
        -------
        bool
            The current value of MetadataEnable.
        """
        return self._get_something_simple(self.at.get_bool, Features.MetadataEnable)

    def set_metadata_enable(self, value):
        """Sets MetadataEnable to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to MetadataEnable.
        """
        self._set_something_simple(self.at.set_bool, Features.MetadataEnable, value)

    def get_metadata_timestamp(self):
        """Gets the current value of MetadataTimestamp.

        Returns
        -------
        bool
            The current value of MetadataTimestamp.
        """
        return self._get_something_simple(self.at.get_bool, Features.MetadataTimestamp)

    def set_metadata_timestamp(self, value):
        """Sets MetadataTimestamp to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to MetadataTimestamp.
        """
        self._set_something_simple(self.at.set_bool, Features.MetadataTimestamp, value)

    def get_metadata_frame(self):
        """Gets the current value of MetadataFrame.

        Returns
        -------
        bool
            The current value of MetadataFrame.
        """
        return self._get_something_simple(self.at.get_bool, Features.MetadataFrame)

    def get_overlap(self):
        """Gets the current value of Overlap.

        Returns
        -------
        bool
            The current value of Overlap.
        """
        return self._get_something_simple(self.at.get_bool, Features.Overlap)

    def set_overlap(self, value):
        """Sets Overlap to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to Overlap.
        """
        self._set_something_simple(self.at.set_bool, Features.Overlap, value)

    def get_pixel_encoding(self):
        """Gets the current value of PixelEncoding.

        Returns
        -------
        str
            The current value of PixelEncoding.
        """
        index = self._get_something_simple(
            self.at.get_enumerated, Features.PixelEncoding
        )
        return self._get_something_with_index(
            self.at.get_enum_string_by_index, Features.PixelEncoding, index
        )

    def get_pixel_encoding_values(self):
        """Gets the possible values of PixelEncoding.

        Returns
        -------
        str[]
            The possible values of PixelEncoding.
        """
        count = self._get_something_simple(
            self.at.get_enum_count, Features.PixelEncoding
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.get_enum_string_by_index, Features.PixelEncoding, i
                )
            )
        return values

    def set_pixel_encoding(self, value):
        """Sets PixelEncoding to the specified value.

        Use get_pixel_encoding_values() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to PixelEncoding.
        """
        valid_values = self.get_pixel__encoding_values()
        if value not in valid_values:
            raise ValueError(
                f"The value {value} is not a valid value for "
                f"PixelEncoding. Valid values are {valid_values}."
            )
        self._set_something_simple(
            self.at.set_enumerated_string, Features.PixelEncoding, value
        )

    def get_pixel_height(self):
        """Gets the current value of PixelHeight.

        Returns
        -------
        float
            The current value of PixelHeight.
        """
        return self._get_something_simple(self.at.get_float, Features.PixelHeight)

    def get_pixel_readout_date(self):
        """Gets the current value of PixelReadoutRate.

        Returns
        -------
        str
            The current value of PixelReadoutRate.
        """
        index = self._get_something_simple(
            self.at.get_enumerated, Features.PixelReadoutRate
        )
        return self._get_something_with_index(
            self.at.get_enum_string_by_index, Features.PixelReadoutRate, index
        )

    def get_pixel_readout_rate_values(self):
        """Gets the possible values of PixelReadoutRate.

        Returns
        -------
        str[]
            The possible values of PixelReadoutRate.
        """
        count = self._get_something_simple(
            self.at.get_enum_count, Features.PixelReadoutRate
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.get_enum_string_by_index, Features.PixelReadoutRate, i
                )
            )
        return values

    def set_pixel_readout_rate(self, value):
        """Sets PixelReadoutRate to the specified value.

        Use get_pixel_readout_rate_values() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to PixelReadoutRate.
        """
        valid_values = self.get_pixel_readout_rate_values()
        if value not in valid_values:
            raise ValueError(
                f"The value {value} is not a valid value for "
                f"PixelReadoutRate. Valid values are {valid_values}."
            )
        self._set_something_simple(
            self.at.set_enumerated_string, Features.PixelReadoutRate, value
        )

    def get_pixel_width(self):
        """Gets the current value of PixelWidth.

        Returns
        -------
        float
            The current value of PixelWidth.
        """
        return self._get_something_simple(self.at.get_float, Features.PixelWidth)

    def get_readout_time(self):
        """Gets the current value of ReadoutTime.

        Returns
        -------
        float
            The current value of ReadoutTime.
        """
        return self._get_something_simple(self.at.get_float, Features.ReadoutTime)

    def get_row_read_time(self):
        """Gets the current value of RowReadTime.

        Returns
        -------
        float
            The current value of RowReadTime.
        """
        return self._get_something_simple(self.at.get_float, Features.RowReadTime)

    def get_sensor_cooling(self):
        """Gets the current value of SensorCooling.

        Returns
        -------
        bool
            The current value of SensorCooling.
        """
        return self._get_something_simple(self.at.get_bool, Features.SensorCooling)

    def set_sensor_pooling(self, value):
        """Sets SensorCooling to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to SensorCooling.
        """
        self._set_something_simple(self.at.set_bool, Features.SensorCooling, value)

    def get_sensor_height(self):
        """Gets the current value of SensorHeight.

        Returns
        -------
        int
            The current value of SensorHeight.
        """
        return self._get_something_simple(self.at.get_int, Features.SensorHeight)

    def get_sensor_temperature(self):
        """Gets the current value of SensorTemperature.

        Returns
        -------
        float
            The current value of SensorTemperature.
        """
        return self._get_something_simple(self.at.get_float, Features.SensorTemperature)

    def get_sensor_width(self):
        """Gets the current value of SensorWidth.

        Returns
        -------
        int
            The current value of SensorWidth.
        """
        return self._get_something_simple(self.at.get_int, Features.SensorWidth)

    def get_serial_number(self):
        """Gets the current value of SerialNumber.

        Returns
        -------
        str
            The current value of SerialNumber.
        """
        return self._get_something_simple(self.at.get_string, Features.SerialNumber)

    def get_shutter_output_mode(self):
        """Gets the current value of ShutterOutputMode.

        Returns
        -------
        str
            The current value of ShutterOutputMode.
        """
        index = self._get_something_simple(
            self.at.get_enumerated, Features.ShutterOutputMode
        )
        return self._get_something_with_index(
            self.at.get_enum_string_by_index, Features.ShutterOutputMode, index
        )

    def get_shutter_output_mode_values(self):
        """Gets the possible values of ShutterOutputMode.

        Returns
        -------
        str[]
            The possible values of ShutterOutputMode.
        """
        count = self._get_something_simple(
            self.at.get_enum_count, Features.ShutterOutputMode
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.get_enum_string_by_index, Features.ShutterOutputMode, i
                )
            )
        return values

    def set_shutter_output_mode(self, value):
        """Sets ShutterOutputMode to the specified value.

        Use get_shutter_output_mode_values() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to ShutterOutputMode.
        """
        valid_values = self.get_shutter_output_mode_values()
        if value not in valid_values:
            raise ValueError(
                f"The value {value} is not a valid value for ShutterOutputMode. Valid "
                f"values are {valid_values}."
            )
        self._set_something_simple(
            self.at.set_enumerated_string, Features.ShutterOutputMode, value
        )

    def get_simple_pre_amp_gain_control(self):
        """Gets the current value of SimplePreAmpGainControl.

        Returns
        -------
        str
            The current value of SimplePreAmpGainControl.
        """
        index = self._get_something_simple(
            self.at.get_enumerated, Features.SimplePreAmpGainControl
        )
        return self._get_something_with_index(
            self.at.get_enum_string_by_index, Features.SimplePreAmpGainControl, index
        )

    def get_simple_pre_amp_gain_control_values(self):
        """Gets the possible values of SimplePreAmpGainControl.

        Returns
        -------
        str[]
            The possible values of SimplePreAmpGainControl.
        """
        count = self._get_something_simple(
            self.at.get_enum_count, Features.SimplePreAmpGainControl
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.get_enum_string_by_index,
                    Features.SimplePreAmpGainControl,
                    i,
                )
            )
        return values

    def set_simple_pre_amp_gain_control(self, value):
        """Sets SimplePreAmpGainControl to the specified value.

        Use get_simple_pre_amp_gain_control_values() to get a list of valid
        values.

        Parameters
        ----------
        value : str
            The value to apply to SimplePreAmpGainControl.
        """
        valid_values = self.get_simple_pre_amp_gain_control_values()
        if value not in valid_values:
            raise ValueError(
                f"The value {value} is not a valid value for "
                f"SimplePreAmpGainControl. Valid values are {valid_values}."
            )
        self._set_something_simple(
            self.at.set_enumerated_string, Features.SimplePreAmpGainControl, value
        )

    def get_shutter_transfer_time(self):
        """Gets the current value of ShutterTransferTime.

        Returns
        -------
        float
            The current value of ShutterTransferTime.
        """
        return self._get_something_simple(
            self.at.get_float, Features.ShutterTransferTime
        )

    def set_shutter_transfer_time(self, value):
        """Sets ShutterTransferTime to the specified value.

        The value specified must pass a min/max check. The allowed values
        are dependent on camera configuration.

        Parameters
        ----------
        value : float
            The value to apply to ShutterTransferTime.
        """
        result, min_value = self.at.get_float_min(
            self.handle, Features.ShutterTransferTime
        )
        result, max_value = self.at.get_float_max(
            self.handle, Features.ShutterTransferTime
        )
        if value < min_value or value > max_value:
            raise ValueError(
                f"Value ({value}) for ShutterTransferTime must be"
                f" between {min_value} and {max_value}."
            )
        self._set_something_simple(
            self.at.set_float, Features.ShutterTransferTime, value
        )

    def cmd_software_trigger(self):
        """Send the SoftwareTrigger command."""
        self._send_command(Features.SoftwareTrigger)

    def get_static_blemish_correction(self):
        """Gets the current value of StaticBlemishCorrection.

        Returns
        -------
        bool
            The current value of StaticBlemishCorrection.
        """
        return self._get_something_simple(
            self.at.get_bool, Features.StaticBlemishCorrection
        )

    def set_static_blemish_correction(self, value):
        """Sets StaticBlemishCorrection to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to StaticBlemishCorrection.
        """
        self._set_something_simple(
            self.at.set_bool, Features.StaticBlemishCorrection, value
        )

    def get_spurious_noise_filter(self):
        """Gets the current value of SpuriousNoiseFilter.

        Returns
        -------
        bool
            The current value of SpuriousNoiseFilter.
        """
        return self._get_something_simple(
            self.at.get_bool, Features.SpuriousNoiseFilter
        )

    def set_spurious_noise_filter(self, value):
        """Sets SpuriousNoiseFilter to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to SpuriousNoiseFilter.
        """
        self._set_something_simple(
            self.at.set_bool, Features.SpuriousNoiseFilter, value
        )

    def get_target_sensor_temperature(self):
        """Gets the current value of TargetSensorTemperature.

        Returns
        -------
        float
            The current value of TargetSensorTemperature.
        """
        return self._get_something_simple(
            self.at.get_float, Features.TargetSensorTemperature
        )

    def get_temperature_control(self):
        """Gets the current value of TemperatureControl.

        Returns
        -------
        str
            The current value of TemperatureControl.
        """
        index = self._get_something_simple(
            self.at.get_enumerated, Features.TemperatureControl
        )
        return self._get_something_with_index(
            self.at.get_enum_string_by_index, Features.TemperatureControl, index
        )

    def get_temperature_control_values(self):
        """Gets the possible values of TemperatureControl.

        Returns
        -------
        str[]
            The possible values of TemperatureControl.
        """
        count = self._get_something_simple(
            self.at.get_enum_count, Features.TemperatureControl
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.get_enum_string_by_index, Features.TemperatureControl, i
                )
            )
        return values

    def get_temperature_status(self):
        """Gets the current value of TemperatureStatus.

        Returns
        -------
        str
            The current value of TemperatureStatus.
        """
        index = self._get_something_simple(
            self.at.get_enumerated, Features.TemperatureStatus
        )
        return self._get_something_with_index(
            self.at.get_enum_string_by_index, Features.TemperatureStatus, index
        )

    def get_temperature_status_values(self):
        """Gets the possible values of TemperatureStatus.

        Returns
        -------
        str[]
            The possible values of TemperatureStatus.
        """
        count = self._get_something_simple(
            self.at.get_enum_count, Features.TemperatureStatus
        )
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.get_enum_string_by_index, Features.TemperatureStatus, i
                )
            )
        return values

    def get_timestamp_clock(self):
        """Gets the current value of TimestampClock.

        Returns
        -------
        int
            The current value of TimestampClock.
        """
        return self._get_something_simple(self.at.get_int, Features.TimestampClock)

    def get_timestamp_clock_frequency(self):
        """Gets the current value of TimestampClockFrequency.

        Returns
        -------
        int
            The current value of TimestampClockFrequency.
        """
        return self._get_something_simple(
            self.at.get_int, Features.TimestampClockFrequency
        )

    def get_trigger_mode(self):
        """Gets the current value of TriggerMode.

        Returns
        -------
        str
            The current value of TriggerMode.
        """
        index = self._get_something_simple(self.at.get_enumerated, Features.TriggerMode)
        return self._get_something_with_index(
            self.at.get_enum_string_by_index, Features.TriggerMode, index
        )

    def get_trigger_mode_values(self):
        """Gets the possible values of TriggerMode.

        Returns
        -------
        str[]
            The possible values of TriggerMode.
        """
        count = self._get_something_simple(self.at.get_enum_count, Features.TriggerMode)
        values = []
        for i in range(count):
            values.append(
                self._get_something_with_index(
                    self.at.get_enum_string_by_index, Features.TriggerMode, i
                )
            )
        return values

    def set_trigger_mode(self, value):
        """Sets TriggerMode to the specified value.

        Use get_trigger_mode_values() to get a list of valid values.

        Parameters
        ----------
        value : str
            The value to apply to TriggerMode.
        """
        valid_values = self.get_trigger_mode_values()
        if value not in valid_values:
            raise ValueError(
                f"The value {value} is not a valid value for TriggerMode. "
                f"Valid values are {valid_values}."
            )
        self._set_something_simple(
            self.at.set_enumerated_string, Features.TriggerMode, value
        )

    def get_vertically_centre_AOI(self):
        """Gets the current value of VerticallyCentreAOI.

        Returns
        -------
        bool
            The current value of VerticallyCentreAOI.
        """
        return self._get_something_simple(
            self.at.get_bool, Features.VerticallyCentreAOI
        )

    def set_vertically_centre_AOI(self, value):
        """Sets VerticallyCentreAOI to the specified value.

        Parameters
        ----------
        value : bool
            The value to apply to VerticallyCentreAOI.
        """
        self._set_something_simple(
            self.at.set_bool, Features.VerticallyCentreAOI, value
        )

    def queue_buffer(self):
        """Adds a data buffer to the internal driver queue.

        Returns
        -------
        ctypes.c_char_p
            The buffer added to the queue.
        """
        self._assert_handle()
        result, buffer = self.at.queue_buffer(self.handle, self.get_image_size_bytes())
        self._raise_if_bad(result)
        return buffer

    def wait_buffer(self, buffer, timeout=60000):
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
        result, bytes_populated = self.at.wait_buffer(self.handle, buffer, timeout)
        self._raise_if_bad(result)
        return bytes_populated

    def flush(self):
        """Flushes the current data buffer queue."""
        self._assert_handle()
        result = self.at.flush(self.handle)
        self._raise_if_bad(result)

    def take(self, frame_count):
        self.flush()
        self.set_frame_count(frame_count)
        buffers = []
        for i in range(frame_count):
            buffers.append(self.queue_buffer())
        self.cmd_acquisition_start()
        for buffer in buffers:
            self.wait_buffer(buffer)
        return buffers

    def take_one(self):
        self.flush()
        buffer = self.queue_buffer()
        self.cmd_acquisition_start()
        self.wait_buffer(buffer)
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
