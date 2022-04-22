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
import pathlib

import numpy as np
import yaml

from . import zwofilterwheel
from .. import exposure
from . import basecamera


class ASICamera(basecamera.BaseCamera):
    def __init__(self, log=None):
        super().__init__(log=log)

        self.lib = ASILibrary()
        self.lib.initialise()
        self.is_live_exposure = False
        self.id = 0
        self.bin_value = 0
        self.normal_image_type = None
        self.current_image_type = None
        self.dev = None
        self.use_zwo_filter_wheel = None
        self.filter_id = None
        self.filter_number = None
        self.zwo_lib = None
        self.zwo_dev = None

    @staticmethod
    def name():
        """Set camera name."""
        return "Zwo"

    def initialise(self, config):
        """Initialise the camera with the specified configuration file.

        Parameters
        ----------
        config : str
            The name of the configuration file to load."""
        self.id = config.id
        self.bin_value = config.bin_value
        self.normal_image_type = getattr(ASIImageType, config.current_image_type)
        self.current_image_type = self.normal_image_type
        self.dev = self.lib.open_ASI(self.id)
        self.set_full_frame()

        self.use_zwo_filter_wheel = config.use_zwo_filter_wheel

        self.filter_id = config.filter_id  # ID of the filter wheel not the filter
        self.filter_number = None

        if self.use_zwo_filter_wheel:
            self.zwo_lib = zwofilterwheel.EFWLibrary()
            self.zwo_lib.initialise()
            self.zwo_dev = self.zwo_lib.open_EFW(self.filter_id)
            # self.zwo_dev.set_position(self.filter_number)
            self.filter_number = self.zwo_lib.get_position(self.filter_id)

    def get_config_schema(self):
        return yaml.safe_load(
            """
$schema: http://json-schema.org/draft-07/schema#
description: Schema for ZWO cameras.
type: object
properties:
  id:
    default: 0
    type: number
    description: The ID of the camera to be set in the FITS header.
  bin_value:
    default: 1
    type: number
    description: The value for how to bin the image pixels.
  current_image_type:
    default: raw16
    type: string
    description: >
      The image type to store. This usually provides informtation about the
      pixel depth, the color space or whether it is a raw image of not.
    enum:
      - raw8
      - rgb24
      - raw16
      - y8
  use_zwo_filter_wheel:
    default: true
    type: boolean
    description: Use the ZWO filter wheel (true) or not (false).
  filter_id:
    default: 1
    type: number
    description: >
      The ID of the filter wheel to use. In general this will be 1 unless more
      than one filter wheel is installed.
  filter_number:
    default: 2
    type: number
    description: >
      The ID of the filter to use. Depending on the type of ZWO filter wheel
      used, this value can have a maximum of 5, 7 or 8.
"""
        )

    def get_make_and_model(self):
        """Get the make and model of the camera.

        Returns
        -------
        str
            The make and model of the camera."""
        info = self.dev.get_camera_info()
        return info.Name

    def get_value(self, key):
        """Gets the value of a unique property of the camera.

        Parameters
        ----------
        key : str
            The name of the property.
        Returns
        -------
        str
            The value of the property.
            Returns 'UNDEFINED' if the property doesn't exist."""
        return super().get_value(key)

    async def set_value(self, key, value):
        """Set a unique property of the camera.

        Parameters
        ----------
        key : str
            The name of the property.
        value : str
            The value of the property."""
        key = key.lower()
        if key == "filter" and self.use_zwo_filter_wheel:
            self.zwo_dev.set_position(int(value))
            self.filter_number = int(value)
            while not self.zwo_dev.is_in_position():
                await asyncio.sleep(0.02)
        await super().set_value(key, value)

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
        left, top = self.dev.get_start_position()
        width, height, binning, img_type = self.dev.get_ROI()
        return top, left, width, height

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
        print(width, height, self.bin_value, self.current_image_type)
        self.dev.set_ROI(width, height, self.bin_value, self.current_image_type)
        self.dev.set_start_position(left, top)

    def set_full_frame(self):
        """Sets the region of interest to the whole sensor."""
        info = self.dev.get_camera_info()
        self.set_roi(
            0,
            0,
            int(info.MaxWidth / self.bin_value),
            int(info.MaxHeight / self.bin_value),
        )

    def start_live_view(self):
        """Configure the camera for live view.

        This should change the image format to 8bits per pixel so
        the image can be encoded to JPEG."""
        # self.current_image_type = ASIImageType.Raw8
        top, left, width, height = self.get_ROI()
        self.set_roi(top, left, width, height)
        self.is_live_exposure = True
        super().start_live_view()

    def stop_live_view(self):
        """Configure the camera for a standard exposure."""
        self.current_image_type = self.normal_image_type
        top, left, width, height = self.get_ROI()
        self.set_roi(top, left, width, height)
        self.is_live_exposure = False
        super().stop_live_view()

    async def start_take_image(self, exp_time, shutter, science, guide, wfs):
        """Start taking an image or a set of images.

        Parameters
        ----------
        exp_time : float
            The exposure time in seconds.
        shutter : bool
            Should the shutter be opened?
        science : bool
            Should the science/main sensor be used?
        guide : bool
            Should guider sensor be used?
        wfs : bool
            Should wave front sensor be used?
        """
        self.dev.set_control_value(
            ASIControlType.Exposure, int(exp_time * 1000000), False
        )
        await super().start_take_image(exp_time, shutter, science, guide, wfs)

    async def start_integration(self):
        """Start integrating."""
        self.dev.start_exposure()
        await super().start_integration()

    async def end_integration(self):
        """End integration.

        This should wait for the integration period to complete."""
        result = self.dev.get_exposure_status()
        while result == ASIExposureStatus.Working:
            await asyncio.sleep(0.02)
            result = self.dev.get_exposure_status()
        if result == ASIExposureStatus.Failed:
            raise ASIImageFailed()
        await super().end_integration()

    async def end_readout(self):
        """Start reading out the image."""
        buffer = self.dev.get_exposure_data()
        buffer_array = np.frombuffer(buffer, dtype=np.uint16)
        exposure_time, auto = self.dev.get_control_value(ASIControlType.Exposure)
        offset, auto = self.dev.get_control_value(ASIControlType.Offset)
        temperature, auto = self.dev.get_control_value(ASIControlType.Temperature)
        cooler_power_percentage, auto = self.dev.get_control_value(
            ASIControlType.CoolerPowerPercentage
        )
        target_temperature, auto = self.dev.get_control_value(
            ASIControlType.TargetTemperature
        )
        cooler_on, auto = self.dev.get_control_value(ASIControlType.CoolerOn)
        top, left, width, height = self.get_ROI()
        tags = {
            "TOP": top,
            "LEFT": left,
            "WIDTH": width,
            "HEIGHT": height,
            "EXPOSURE": (exposure_time / 1000000.0),
            "OFFSET": offset,
            "TEMPERATURE": (temperature / 10.0),
            "COOLER_POWER_PERCENTAGE": cooler_power_percentage,
            "TARGET_TEMPERATURE": target_temperature,
            "COOLER_ON": cooler_on,
        }
        await super().start_readout()
        image = exposure.Exposure(buffer_array, width, height, tags)
        return image


class ASIBayerPattern(enum.Enum):
    RG = 0
    BG = 1
    GR = 2
    GB = 3


class ASIImageType(enum.Enum):
    Raw8 = 0
    RGB24 = 1
    Raw16 = 2
    Y8 = 3
    End = -1


class ASIGuideDirection(enum.Enum):
    North = 0
    South = 1
    East = 2
    West = 3


class ASIFlip(enum.Enum):
    NoFlip = 0
    Horizontal = 1
    Vertical = 2
    Both = 3


class ASICameraMode(enum.Enum):
    Normal = 0
    TriggerSoftEdge = 1
    TriggerRisingEdge = 2
    TriggerFallingEdge = 3
    TriggerSoftLevel = 4
    TriggerHighLevel = 5
    TriggerLowLevel = 6
    End = -1


class Results(enum.Enum):
    Success = 0
    InvalidIndex = 1
    InvalidId = 2
    InvalidControlType = 3
    CameraClosed = 4
    CameraRemoved = 5
    InvalidPath = 6
    InvalidFileFormat = 7
    InvalidSize = 8
    InvalidImgType = 9
    OutOfBoundary = 10
    Timeout = 11
    InvalidSequence = 12
    BufferTooSmall = 13
    VideoModeActive = 14
    ExposureInProgress = 15
    GeneralError = 16
    InvalidMode = 17
    End = 18


class ASICameraInfo:
    def __init__(self, info):
        self.Name = info.Name.decode("ascii")
        self.CameraID = int(info.CameraID)
        self.MaxHeight = int(info.MaxHeight)
        self.MaxWidth = int(info.MaxWidth)
        self.IsColorCam = bool(info.IsColorCam)
        self.BayerPattern = ASIBayerPattern(info.BayerPattern)
        self.SupportedBins = [x for x in info.SupportedBins if x != 0]
        video_formats = []
        for x in info.SupportedVideoFormat:
            if x == -1:
                break
            video_formats.append(ASIImageType(x))
        self.SupportedVideoFormat = video_formats
        self.PixelSize = float(info.PixelSize)
        self.MechanicalShutter = bool(info.MechanicalShutter)
        self.ST4Port = bool(info.ST4Port)
        self.IsColorCam = bool(info.IsColorCam)
        self.IsUSB3Host = bool(info.IsUSB3Host)
        self.IsUSB3Camera = bool(info.IsUSB3Camera)
        self.ElecPerADU = float(info.ElecPerADU)
        self.BitDepth = int(info.BitDepth)
        self.IsTriggerCam = bool(info.IsTriggerCam)


# This class was taken from https://github.com/stevemarple/python-zwoasi
class ASICameraInfoCtypes(ctypes.Structure):
    _fields_ = [
        ("Name", ctypes.c_char * 64),
        ("CameraID", ctypes.c_int),
        ("MaxHeight", ctypes.c_long),
        ("MaxWidth", ctypes.c_long),
        ("IsColorCam", ctypes.c_int),
        ("BayerPattern", ctypes.c_int),
        ("SupportedBins", ctypes.c_int * 16),
        ("SupportedVideoFormat", ctypes.c_int * 8),
        ("PixelSize", ctypes.c_double),  # in um
        ("MechanicalShutter", ctypes.c_int),
        ("ST4Port", ctypes.c_int),
        ("IsCoolerCam", ctypes.c_int),
        ("IsUSB3Host", ctypes.c_int),
        ("IsUSB3Camera", ctypes.c_int),
        ("ElecPerADU", ctypes.c_float),
        ("BitDepth", ctypes.c_int),
        ("IsTriggerCam", ctypes.c_int),
        ("Unused", ctypes.c_char * 16),
    ]


class ASIControlType(enum.Enum):
    Gain = 0
    Exposure = 1
    Gamma = 2
    WB_R = 3
    WB_B = 4
    Offset = 5
    BandwidthOverload = 6
    Overclock = 7
    Temperature = 8  # Return 10 * temperature
    Flip = 9
    AutoMaxGain = 10
    AutoMaxExposure = 11  # Micro Second
    AutoTargetBrightness = 12
    HardwareBin = 13
    HighSpeedMode = 14
    CoolerPowerPercentage = 15
    TargetTemperature = 16  # Not *10
    CoolerOn = 17
    MonoBin = 18
    FanOn = 19
    PatternAdjust = 20
    AntiDewHeater = 21


class ASIControlCaps:
    def __init__(self, caps):
        self.Name = caps.Name.decode("ascii")
        self.Description = caps.Description.decode("ascii")
        self.MaxValue = int(caps.MaxValue)
        self.MinValue = int(caps.MinValue)
        self.DefaultValue = int(caps.DefaultValue)
        self.IsAutoSupported = bool(caps.IsAutoSupported)
        self.IsWritable = bool(caps.IsWritable)
        self.ControlType = ASIControlType(caps.ControlType)


# This class was taken from https://github.com/stevemarple/python-zwoasi
class ASIControlCapsCtypes(ctypes.Structure):
    _fields_ = [
        ("Name", ctypes.c_char * 64),
        ("Description", ctypes.c_char * 128),
        ("MaxValue", ctypes.c_long),
        ("MinValue", ctypes.c_long),
        ("DefaultValue", ctypes.c_long),
        ("IsAutoSupported", ctypes.c_int),
        ("IsWritable", ctypes.c_int),
        ("ControlType", ctypes.c_int),
        ("Unused", ctypes.c_char * 32),
    ]


class ASIExposureStatus(enum.Enum):
    Idle = 0
    Working = 1
    Success = 2
    Failed = 3


class ASIID:
    def __init__(self, id):
        self.ID = id.id.decode("ascii")


# This class was taken from https://github.com/stevemarple/python-zwoasi
class ASIIDCtypes(ctypes.Structure):
    _fields_ = [("id", ctypes.c_char * 8)]


class ASISupportedMode:
    def __init__(self, mode):
        self.SupportedCameraMode = [
            ASICameraMode(mode.SupportedCameraMode[i]) for i in range(16)
        ]


class ASISupportedModeCtypes(ctypes.Structure):
    _fields_ = [("SupportedCameraMode", ctypes.c_int * 16)]


class ASI:
    def __init__(self):
        lib = ctypes.CDLL(
            pathlib.Path(__file__).resolve().parent.joinpath("libASICamera2.so")
        )

        # ASICAMERA_API  int ASIGetNumOfConnectedCameras();
        lib.ASIGetNumOfConnectedCameras.restype = ctypes.c_int

        # ASICAMERA_API int ASIGetProductIDs(int* pPIDs);
        lib.ASIGetProductIDs.argtypes = [ctypes.c_int * 256]
        lib.ASIGetProductIDs.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE ASIGetCameraProperty(ASI_CAMERA_INFO
        # *pASICameraInfo, int iCameraIndex);
        lib.ASIGetCameraProperty.argtypes = [
            ctypes.POINTER(ASICameraInfoCtypes),
            ctypes.c_int,
        ]
        lib.ASIGetCameraProperty.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE ASIGetCameraPropertyByID(int iCameraID,
        # ASI_CAMERA_INFO *pASICameraInfo);
        lib.ASIGetCameraPropertyByID.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(ASICameraInfoCtypes),
        ]
        lib.ASIGetCameraPropertyByID.restype = ctypes.c_int

        # ASICAMERA_API  ASI_ERROR_CODE ASIOpenCamera(int iCameraID);
        lib.ASIOpenCamera.argtypes = [ctypes.c_int]
        lib.ASIOpenCamera.restype = ctypes.c_int

        # ASICAMERA_API  ASI_ERROR_CODE ASIInitCamera(int iCameraID);
        lib.ASIInitCamera.argtypes = [ctypes.c_int]
        lib.ASIInitCamera.restype = ctypes.c_int

        # ASICAMERA_API  ASI_ERROR_CODE ASICloseCamera(int iCameraID);
        lib.ASICloseCamera.argtypes = [ctypes.c_int]
        lib.ASICloseCamera.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE ASIGetNumOfControls(int iCameraID,
        # int * piNumberOfControls);
        lib.ASIGetNumOfControls.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        lib.ASIGetNumOfControls.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE ASIGetControlCaps(int iCameraID,
        # int iControlIndex, ASI_CONTROL_CAPS * pControlCaps);
        lib.ASIGetControlCaps.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ASIControlCapsCtypes),
        ]
        lib.ASIGetControlCaps.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE ASIGetControlValue(int  iCameraID,
        # ASI_CONTROL_TYPE  ControlType, long *plValue, ASI_BOOL *pbAuto);
        lib.ASIGetControlValue.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_long),
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.ASIGetControlValue.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE ASISetControlValue(int  iCameraID,
        # ASI_CONTROL_TYPE  ControlType, long lValue, ASI_BOOL bAuto);
        lib.ASISetControlValue.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_long,
            ctypes.c_int,
        ]
        lib.ASISetControlValue.restype = ctypes.c_int

        # ASICAMERA_API  ASI_ERROR_CODE ASISetROIFormat(int iCameraID,
        # int iWidth, int iHeight,  int iBin, ASI_IMG_TYPE Img_type);
        lib.ASISetROIFormat.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        ]
        lib.ASISetROIFormat.restype = ctypes.c_int

        # ASICAMERA_API  ASI_ERROR_CODE ASIGetROIFormat(int iCameraID,
        # int *piWidth, int *piHeight,  int *piBin, ASI_IMG_TYPE *pImg_type);
        lib.ASIGetROIFormat.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.ASIGetROIFormat.restype = ctypes.c_int

        # ASICAMERA_API  ASI_ERROR_CODE ASISetStartPos(int iCameraID,
        # int iStartX, int iStartY);
        lib.ASISetStartPos.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
        lib.ASISetStartPos.restype = ctypes.c_int

        # ASICAMERA_API  ASI_ERROR_CODE ASIGetStartPos(int iCameraID,
        # int *piStartX, int *piStartY);
        lib.ASIGetStartPos.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.ASIGetStartPos.restype = ctypes.c_int

        # ASICAMERA_API  ASI_ERROR_CODE ASIGetDroppedFrames(int iCameraID,
        # int *piDropFrames);
        lib.ASIGetDroppedFrames.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        lib.ASIGetDroppedFrames.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE ASIEnableDarkSubtract(int iCameraID,
        # char *pcBMPPath);
        lib.ASIEnableDarkSubtract.argtypes = [ctypes.c_int, ctypes.c_char_p]
        lib.ASIEnableDarkSubtract.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE ASIDisableDarkSubtract(int iCameraID);
        lib.ASIDisableDarkSubtract.argtypes = [ctypes.c_int]
        lib.ASIDisableDarkSubtract.restype = ctypes.c_int

        # ASICAMERA_API  ASI_ERROR_CODE ASIStartVideoCapture(int iCameraID);
        lib.ASIStartVideoCapture.argtypes = [ctypes.c_int]
        lib.ASIStartVideoCapture.restype = ctypes.c_int

        # ASICAMERA_API  ASI_ERROR_CODE ASIStopVideoCapture(int iCameraID);
        lib.ASIStopVideoCapture.argtypes = [ctypes.c_int]
        lib.ASIStopVideoCapture.restype = ctypes.c_int

        # ASICAMERA_API  ASI_ERROR_CODE ASIGetVideoData(int iCameraID,
        # unsigned char* pBuffer, long lBuffSize, int iWaitms);
        lib.ASIGetVideoData.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_long,
            ctypes.c_int,
        ]
        lib.ASIGetVideoData.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE ASIPulseGuideOn(int iCameraID,
        # ASI_GUIDE_DIRECTION direction);
        lib.ASIPulseGuideOn.argtypes = [ctypes.c_int, ctypes.c_int]
        lib.ASIPulseGuideOn.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE ASIPulseGuideOff(int iCameraID,
        # ASI_GUIDE_DIRECTION direction);
        lib.ASIPulseGuideOff.argtypes = [ctypes.c_int, ctypes.c_int]
        lib.ASIPulseGuideOff.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE  ASIStartExposure(int iCameraID,
        # ASI_BOOL bIsDark);
        lib.ASIStartExposure.argtypes = [ctypes.c_int, ctypes.c_int]
        lib.ASIStartExposure.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE  ASIStopExposure(int iCameraID);
        lib.ASIStopExposure.argtypes = [ctypes.c_int]
        lib.ASIStopExposure.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE  ASIGetExpStatus(int iCameraID,
        # ASI_EXPOSURE_STATUS *pExpStatus);
        lib.ASIGetExpStatus.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        lib.ASIGetExpStatus.restype = ctypes.c_int

        # ASICAMERA_API  ASI_ERROR_CODE ASIGetDataAfterExp(int iCameraID,
        # unsigned char* pBuffer, long lBuffSize);
        lib.ASIGetDataAfterExp.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_long]
        lib.ASIGetDataAfterExp.restype = ctypes.c_int

        # ASICAMERA_API  ASI_ERROR_CODE ASIGetID(int iCameraID, ASI_ID* pID);
        lib.ASIGetID.argtypes = [ctypes.c_int, ctypes.POINTER(ASIIDCtypes)]
        lib.ASIGetID.restype = ctypes.c_int

        # ASICAMERA_API  ASI_ERROR_CODE ASISetID(int iCameraID, ASI_ID ID);
        lib.ASISetID.argtypes = [ctypes.c_int, ctypes.POINTER(ASIIDCtypes)]
        lib.ASISetID.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE ASIGetGainOffset(int iCameraID,
        # int *pOffset_HighestDR, int *pOffset_UnityGain, int *pGain_LowestRN,
        # int *pOffset_LowestRN);
        lib.ASIGetGainOffset.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.ASIGetGainOffset.restype = ctypes.c_int

        # ASICAMERA_API char* ASIGetSDKVersion();
        lib.ASIGetSDKVersion.restype = ctypes.c_char_p

        # ASICAMERA_API ASI_ERROR_CODE  ASIGetCameraSupportMode(int iCameraID,
        # ASI_SUPPORTED_MODE* pSupportedMode);
        lib.ASIGetCameraSupportMode.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(ASISupportedModeCtypes),
        ]
        lib.ASIGetCameraSupportMode.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE  ASIGetCameraMode(int iCameraID,
        # ASI_CAMERA_MODE* mode);
        lib.ASIGetCameraMode.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        lib.ASIGetCameraMode.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE  ASISetCameraMode(int iCameraID,
        # ASI_CAMERA_MODE mode);
        lib.ASISetCameraMode.argtypes = [ctypes.c_int, ctypes.c_int]
        lib.ASISetCameraMode.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE  ASISendSoftTrigger(int iCameraID,
        # ASI_BOOL bStart);
        lib.ASISendSoftTrigger.argtypes = [ctypes.c_int, ctypes.c_int]
        lib.ASISendSoftTrigger.restype = ctypes.c_int

        # ASICAMERA_API ASI_ERROR_CODE  ASIGetSerialNumber(int iCameraID,
        # ASI_SN* pSN);
        lib.ASIGetSerialNumber.argtypes = [ctypes.c_int, ctypes.POINTER(ASIIDCtypes)]
        lib.ASIGetSerialNumber.restype = ctypes.c_int

        self.lib = lib
        self.int_ptr = ctypes.POINTER(ctypes.c_int)
        self.long_ptr = ctypes.POINTER(ctypes.c_long)

    def get_num_of_connected_cameras(self):
        # ASICAMERA_API  int ASIGetNumOfConnectedCameras();
        return self.lib.ASIGetNumOfConnectedCameras()

    def get_product_IDs(self):
        # ASICAMERA_API int ASIGetProductIDs(int* pPIDs);
        data_type = ctypes.c_int * 256
        product_IDs = data_type()
        count = self.lib.ASIGetProductIDs(product_IDs)
        return [product_IDs[i] for i in range(count)]

    def get_camera_property(self, index):
        # ASICAMERA_API ASI_ERROR_CODE ASIGetCameraProperty(ASI_CAMERA_INFO
        # *pASICameraInfo, int iCameraIndex);
        camera_property = ASICameraInfoCtypes()
        result = self.lib.ASIGetCameraProperty(camera_property, index)
        return self._to_result_enum(result), ASICameraInfo(camera_property)

    def get_camera_property_by_ID(self, id):
        # ASICAMERA_API ASI_ERROR_CODE ASIGetCameraPropertyByID(int iCameraID,
        # ASI_CAMERA_INFO *pASICameraInfo);
        camera_property = ASICameraInfoCtypes()
        result = self.lib.ASIGetCameraPropertyByID(id, camera_property)
        return self._to_result_enum(result), ASICameraInfo(camera_property)

    def open_camera(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIOpenCamera(int iCameraID);
        result = self.lib.ASIOpenCamera(id)
        return self._to_result_enum(result)

    def init_camera(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIInitCamera(int iCameraID);
        result = self.lib.ASIInitCamera(id)
        return self._to_result_enum(result)

    def close_camera(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASICloseCamera(int iCameraID);
        result = self.lib.ASICloseCamera(id)
        return self._to_result_enum(result)

    def get_number_of_controls(self, id):
        # ASICAMERA_API ASI_ERROR_CODE ASIGetNumOfControls(int iCameraID,
        # int * piNumberOfControls);
        number_of_controls = self._get_int_ptr()
        result = self.lib.ASIGetNumOfControls(id, number_of_controls)
        return self._to_result_enum(result), number_of_controls[0]

    def get_control_caps(self, id, index):
        # ASICAMERA_API ASI_ERROR_CODE ASIGetControlCaps(int iCameraID,
        # int iControlIndex, ASI_CONTROL_CAPS * pControlCaps);
        control_caps = ASIControlCapsCtypes()
        result = self.lib.ASIGetControlCaps(id, index, control_caps)
        return self._to_result_enum(result), ASIControlCaps(control_caps)

    def get_control_value(self, id, control_type):
        # ASICAMERA_API ASI_ERROR_CODE ASIGetControlValue(int  iCameraID,
        # ASI_CONTROL_TYPE  ControlType, long *plValue, ASI_BOOL *pbAuto);
        value = self._get_long_ptr()
        auto = self._get_int_ptr()
        result = self.lib.ASIGetControlValue(id, control_type, value, auto)
        return self._to_result_enum(result), value[0], auto[0]

    def set_control_value(self, id, control_type, value, auto):
        # ASICAMERA_API ASI_ERROR_CODE ASISetControlValue(int  iCameraID,
        # ASI_CONTROL_TYPE  ControlType, long lValue, ASI_BOOL bAuto);
        result = self.lib.ASISetControlValue(id, control_type, value, auto)
        return self._to_result_enum(result)

    def set_ROI_format(self, id, width, height, bin, img_type):
        # ASICAMERA_API  ASI_ERROR_CODE ASISetROIFormat(int iCameraID,
        # int iWidth, int iHeight,  int iBin, ASI_IMG_TYPE Img_type);
        result = self.lib.ASISetROIFormat(id, width, height, bin, img_type)
        return self._to_result_enum(result)

    def get_ROI_format(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIGetROIFormat(int iCameraID,
        # int *piWidth, int *piHeight,  int *piBin, ASI_IMG_TYPE *pImg_type);
        width = self._get_int_ptr()
        height = self._get_int_ptr()
        bin = self._get_int_ptr()
        img_type = self._get_int_ptr()
        result = self.lib.ASIGetROIFormat(id, width, height, bin, img_type)
        return self._to_result_enum(result), width[0], height[0], bin[0], img_type[0]

    def set_start_position(self, id, x, y):
        # ASICAMERA_API  ASI_ERROR_CODE ASISetStartPos(int iCameraID, int
        # StartX, int iStartY);
        result = self.lib.ASISetStartPos(id, x, y)
        return self._to_result_enum(result)

    def get_start_position(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIGetStartPos(int CameraID, int
        # *piStartX, int *piStartY);
        x = self._get_int_ptr()
        y = self._get_int_ptr()
        result = self.lib.ASIGetStartPos(id, x, y)
        return self._to_result_enum(result), x[0], y[0]

    def get_dropped_frames(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIGetDroppedFrames(int iCameraID,int
        # *piDropFrames);
        drop_frames = self._get_int_ptr()
        result = self.lib.ASIGetDroppedFrames(id, drop_frames)
        return self._to_result_enum(result), drop_frames[0]

    def enable_dark_subtract(self, id, bmp_file):
        # ASICAMERA_API ASI_ERROR_CODE ASIEnableDarkSubtract(int iCameraID,
        # char *pcBMPPath);
        bmp_file_path = self.get_string_buffer(bmp_file.encode("ascii"))
        result = self.lib.ASIEnableDarkSubtract(id, bmp_file_path)
        return self._to_result_enum(result)

    def disable_dark_subtract(self, id):
        # ASICAMERA_API ASI_ERROR_CODE ASIDisableDarkSubtract(int iCameraID);
        result = self.lib.ASIDisableDarkSubtract(id)
        return self._to_result_enum(result)

    def start_video_capture(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIStartVideoCapture(int iCameraID);
        result = self.lib.ASIStartVideoCapture(id)
        return self._to_result_enum(result)

    def stop_video_capture(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIStopVideoCapture(int iCameraID);
        result = self.lib.ASIStopVideoCapture(id)
        return self._to_result_enum(result)

    def get_video_data(self, id, buffer, buffer_size, timeout_ms):
        # ASICAMERA_API  ASI_ERROR_CODE ASIGetVideoData(int iCameraID,
        # unsigned char* pBuffer, long lBuffSize, int iWaitms);
        result = self.lib.ASIGetVideoData(id, buffer, buffer_size, timeout_ms)
        return self._to_result_enum(result)

    def pulse_guide_on(self, id, direction):
        # ASICAMERA_API ASI_ERROR_CODE ASIPulseGuideOn(int iCameraID,
        # ASI_GUIDE_DIRECTION direction);
        result = self.lib.ASIPulseGuideOn(id, direction)
        return self._to_result_enum(result)

    def pulse_guide_off(self, id, direction):
        # ASICAMERA_API ASI_ERROR_CODE ASIPulseGuideOff(int iCameraID,
        # ASI_GUIDE_DIRECTION direction);
        result = self.lib.ASIPulseGuideOff(id, direction)
        return self._to_result_enum(result)

    def start_exposure(self, id, is_dark):
        # ASICAMERA_API ASI_ERROR_CODE  ASIStartExposure(int iCameraID,
        # ASI_BOOL bIsDark);
        result = self.lib.ASIStartExposure(id, is_dark)
        return self._to_result_enum(result)

    def stop_exposure(self, id):
        # ASICAMERA_API ASI_ERROR_CODE  ASIStopExposure(int iCameraID);
        result = self.lib.ASIStopExposure(id)
        return self._to_result_enum(result)

    def get_exposure_status(self, id):
        # ASICAMERA_API ASI_ERROR_CODE  ASIGetExpStatus(int iCameraID,
        # ASI_EXPOSURE_STATUS *pExpStatus);
        exposure_status = self._get_int_ptr()
        result = self.lib.ASIGetExpStatus(id, exposure_status)
        return self._to_result_enum(result), exposure_status[0]

    def get_data_after_exposure(self, id, buffer, buffer_size):
        # ASICAMERA_API  ASI_ERROR_CODE ASIGetDataAfterExp(int iCameraID,
        # unsigned char* pBuffer, long lBuffSize);
        result = self.lib.ASIGetDataAfterExp(id, buffer, buffer_size)
        return self._to_result_enum(result)

    def get_ID(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIGetID(int iCameraID, ASI_ID* pID);
        other_ID = ASIIDCtypes()
        result = self.lib.ASIGetID(id, other_ID)
        return self._to_result_enum(result), ASIID(other_ID)

    def set_ID(self, id, other_ID):
        # ASICAMERA_API  ASI_ERROR_CODE ASISetID(int iCameraID, ASI_ID ID);
        result = self.lib.ASISetID(id, other_ID)
        return self._to_result_enum(result)

    def get_gain_offset(self, id):
        # ASICAMERA_API ASI_ERROR_CODE ASIGetGainOffset(int iCameraID, int
        # *pOffset_HighestDR, int *pOffset_UnityGain, int *pGain_LowestRN,
        # int *pOffset_LowestRN);
        offset_highest_DR = self._get_int_ptr()
        offset_unity_gain = self._get_int_ptr()
        gain_lowest_RN = self._get_int_ptr()
        offset_lowest_RN = self._get_int_ptr()
        result = self.lib.ASIGetGainOffset(
            id, offset_highest_DR, offset_unity_gain, gain_lowest_RN, offset_lowest_RN
        )
        return (
            self._to_result_enum(result),
            offset_highest_DR[0],
            offset_unity_gain[0],
            gain_lowest_RN[0],
            offset_lowest_RN[0],
        )

    def get_SDK_version(self):
        # ASICAMERA_API char* ASIGetSDKVersion();
        return self.lib.ASIGetSDKVersion().decode("ascii")

    def get_camera_support_mode(self, id):
        # ASICAMERA_API ASI_ERROR_CODE  ASIGetCameraSupportMode(int iCameraID,
        # ASI_SUPPORTED_MODE* pSupportedMode);
        supported_mode = ASISupportedModeCtypes()
        result = self.lib.ASIGetCameraSupportMode(id, supported_mode)
        return self._to_result_enum(result), ASISupportedMode(supported_mode)

    def get_camera_mode(self, id):
        # ASICAMERA_API ASI_ERROR_CODE  ASIGetCameraMode(int iCameraID,
        # ASI_CAMERA_MODE* mode);
        mode = self._get_int_ptr()
        result = self.lib.ASIGetCameraMode(id, mode)
        return self._to_result_enum(result), ASICameraMode(mode[0])

    def set_camera_mode(self, id, mode):
        # ASICAMERA_API ASI_ERROR_CODE  ASISetCameraMode(int iCameraID,
        # ASI_CAMERA_MODE mode);
        result = self.lib.ASISetCameraMode(id, mode)
        return self._to_result_enum(result)

    def send_software_trigger(self, id, start):
        # ASICAMERA_API ASI_ERROR_CODE  ASISendSoftTrigger(int iCameraID,
        # ASI_BOOL bStart);
        result = self.lib.ASISendSoftTrigger(id, start)
        return self._to_result_enum(result)

    def get_serial_number(self, id):
        # ASICAMERA_API ASI_ERROR_CODE  ASIGetSerialNumber(int iCameraID,
        # ASI_SN* pSN);
        serial_number = ASIIDCtypes()
        result = self.lib.ASIGetSerialNumber(id, serial_number)
        return self._to_result_enum(result), ASIID(serial_number)

    def _get_int_ptr(self, default_value=0):
        return self.int_ptr(ctypes.c_int(default_value))

    def _get_long_ptr(self, default_value=0):
        return self.long_ptr(ctypes.c_long(default_value))

    def _to_result_enum(self, result):
        return Results(result)

    def get_string_buffer(self, size=128):
        return ctypes.create_string_buffer(size)


class ASIError(Exception):
    def __init__(self, result: Results):
        super().__init__()
        self.result = result

    def __str__(self):
        return self.result.name


class ASILibraryNotInitialised(Exception):
    def __init__(self):
        super().__init__()


class ASIDeviceNotOpenError(Exception):
    def __init__(self):
        super().__init__()


class ASIImageFailed(Exception):
    def __init__(self):
        super().__init__()


class ASIBase(object):
    def __init__(self, asi=None):
        if asi is None:
            self.asi = ASI()
        else:
            self.asi = asi

    def _raise_if_bad(self, result: Results):
        if result != Results.Success:
            raise ASIError(result)


class ASILibrary(ASIBase):
    def __init__(self, asi=None):
        super().__init__(asi)
        self.initialised = False

    def initialise(self):
        """Initialise the ASICamera2 Library."""
        if not self.initialised:
            self.asi.get_num_of_connected_cameras()
            self.initialised = True

    def get_device_count(self):
        """Gets the number of ASI cameras attached to this machine.

        Returns
        -------
        int
            The number of cameras attached to this machine."""
        self._assert_initialised()
        device_count = self.asi.get_num_of_connected_cameras()
        return device_count

    def get_product_IDs(self):
        """Gets the product IDs of all the ASI cameras attached to this
        machine.

        Returns
        -------
        int list
            The product IDs of the cameras attached to this machine."""
        self._assertInitialised()
        product_IDs = self.asi.get_product_IDs()
        return product_IDs

    def get_camera_info(self, index):
        """Gets camera information for the ASI camera at the specified index.

        Parameters
        ----------
        index : int
            The index of the camera (0, get_devicei_count()).

        Returns
        -------
        ASICameraInfo
            The camera information."""
        self._assert_initialised()
        result, camera_info = self.asi.get_camera_property(index)
        self._raise_if_bad(result)
        return camera_info

    def get_SDK_version(self):
        """Gets the SDK version for the library.

        Returns
        -------
        str
            The version of the SDK."""
        self._assert_initialised()
        return self.asi.get_SDK_version()

    def open_ASI(self, index):
        """Opens the specified ASI camera attached to this machine.

        Parameters
        ----------
        index : int
            The index (0 to get_device_count()) of the camera to open.

        Returns
        -------
        ASIDevice
            The camera device."""
        self._assert_initialised()
        device = ASIDevice(index, self.asi)
        return device

    def _assert_initialised(self):
        if not self.initialised:
            raise ASILibraryNotInitialised()


class ASIDevice(ASIBase):
    def __init__(self, index, asi=None):
        super().__init__(asi)
        self.handle = -1
        result = self.asi.open_camera(index)
        self._raise_if_bad(result)
        result = self.asi.init_camera(index)
        self.handle = index

    def close(self):
        """Closes this device."""
        self._assert_handle()
        result = self.asi.close_camera(self.handle)
        self._raise_if_bad(result)
        self.handle = -1

    def get_camera_info(self):
        """Gets camera information for this ASI camera.

        Returns
        -------
        ASICameraInfo
            The camera information."""
        self._assert_handle()
        result, camera_info = self.asi.get_camera_property_by_ID(self.handle)
        self._raise_if_bad(result)
        return camera_info

    def get_number_of_controls(self):
        """Gets the number of controls available for this ASI camera.

        Returns
        -------
        int
            The number of controls available."""
        self._assert_handle()
        result, control_count = self.asi.get_number_of_controls(self.handle)
        self._raise_if_bad(result)
        return control_count

    def get_control_info(self, index):
        """Gets the information on the control at the specified index.

        Parameters
        ----------
        index : int
            The index of the control (0, get_number_of_controls()).

        Returns
        -------
        ASIControlCaps
            The information on the specified control."""
        self._assert_handle()
        result, control_info = self.asi.get_control_caps(self.handle, index)
        self._raise_if_bad(result)
        return control_info

    def get_control_value(self, control_type: ASIControlType):
        """Gets the value of the specified control.

        Parameters
        ----------
        control_type : ASIControlType
            The control to query.

        Returns
        -------
        int
            The value of the control.
        bool
            True if the control is set to auto."""
        self._assert_handle()
        result, value, auto = self.asi.get_control_value(
            self.handle, control_type.value
        )
        self._raise_if_bad(result)
        return value, auto

    def set_control_value(self, control_type: ASIControlType, value, auto: bool):
        """Sets the value of the specified control.

        Parameters
        ----------
        control_type : ASIControlType
            The control to set.
        value : int
            The new value of the control.
        auto : bool
            True if the control should be set automatically."""
        self._assert_handle()
        result = self.asi.set_control_value(
            self.handle, control_type.value, value, self.bool_to_int(auto)
        )
        self._raise_if_bad(result)

    def set_ROI(self, width, height, bin, img_type: ASIImageType):
        """Sets the region of interest, binning, and image type.

        Parameters
        ----------
        width : int
            The width of the region.
        height : int
            The height of the region.
        bin : int
            The bin size for the region.
        img_type : ASIImageType
            The image format."""
        self._assert_handle()
        result = self.asi.set_ROI_format(
            self.handle, width, height, bin, img_type.value
        )
        self._raise_if_bad(result)

    def get_ROI(self):
        """Gets the region of interest, binning, and image type.

        Returns
        -------
        int
            The width of the region.
        int
            The height of the region.
        int
            The pixel binning of the region.
        ASIImageType
            The image type."""
        self._assert_handle()
        result, width, height, bin, img_type = self.asi.get_ROI_format(self.handle)
        self._raise_if_bad(result)
        return width, height, bin, ASIImageType(img_type)

    def set_start_position(self, x, y):
        """Sets the start position of the region of interest.

        Parameters
        ----------
        x : int
            The x position.
        y : int
            The y position."""
        self._assert_handle()
        result = self.asi.set_start_position(self.handle, x, y)
        self._raise_if_bad(result)

    def get_start_position(self):
        """Gets the start position of the region of interest.

        Returns
        -------
        int
            The x position.
        int
            The y position."""
        self._assert_handle()
        result, x, y = self.asi.get_start_position(self.handle)
        self._raise_if_bad(result)
        return x, y

    def get_dropped_frames(self):
        """Gets the number of frames dropped by the camera.

        Returns
        -------
        int
            The number of dropped frames."""
        self._assert_handle()
        result, dropped_frames = self.asi.get_dropped_frames(self.handle)
        self._raise_if_bad(result)
        return dropped_frames

    def enable_dark_subtract(self, bmp_path):
        """Enables the camera to automatically subtract a dark frame.

        Parameters
        ----------
        bmp_path : str
            The path to the dark image as a bitmap."""
        self._assert_handle()
        result = self.asi.enable_dark_subtract(self.handle, bmp_path)
        self._raise_if_bad(result)

    def disable_dark_subtract(self):
        """Disables the automatic subtraction of a dark frame."""
        self._assert_handle()
        result = self.asi.disable_dark_subtract(self.handle)
        self._raise_if_bad(result)

    def start_video_capture(self):
        """Starts capturing video."""
        self._assert_handle()
        result = self.asi.start_video_capture(self.handle)
        self._raise_if_bad(result)

    def stop_video_capture(self):
        """Stops capturing video."""
        self._assert_handle()
        result = self.asi.stop_video_capture(self.handle)
        self._raise_if_bad(result)

    def get_video_data(self):
        """Gets video data.

        Returns
        -------
        buffer
            The image data."""
        self._assert_handle()
        buffer_size = self.get_image_size()
        buffer = self.asi.get_string_buffer(buffer_size)
        exposure_time_in_us = self.get_control_value(ASIControlType.Exposure)
        timeout_in_ms = int((exposure_time_in_us * 2 + 500000) / 1000)
        result = self.asi.get_videoData(self.handle, buffer, buffer_size, timeout_in_ms)
        self._raise_if_bad(result)
        return buffer

    def pulse_guide_on(self, direction: ASIGuideDirection):
        """Issues a guide pulse on the ST4 port for the
        specified direction.

        Parameters
        ----------
        direction : ASIGuideDirection
            The direction to start the pulse."""
        self._assert_handle()
        result = self.asi.pulse_guide_on(self.handle, direction.value)
        self._raise_if_bad(result)

    def pulse_guide_off(self, direction: ASIGuideDirection):
        """Stops issuing a guide pulse on the ST4 port for the
        specified direction.

        Parameters
        ----------
        direction : ASIGuideDirection
            The direction to start the pulse."""
        self._assert_handle()
        result = self.asi.pulse_guide_off(self.handle, direction.value)
        self._raise_if_bad(result)

    def start_exposure(self, is_dark=False):
        """Starts an exposure.

        Parameters
        ----------
        is_dark : bool (optional)
            If true uses the mechanical shutter to take a dark (if available).
        """
        self._assert_handle()
        result = self.asi.start_exposure(self.handle, self.bool_to_int(is_dark))
        self._raise_if_bad(result)

    def stop_exposure(self):
        """Stops an exposure."""
        self._assert_handle()
        result = self.asi.stop_exposure(self.handle)
        self._raise_if_bad(result)

    def get_exposure_status(self):
        """Gets the status of a currently running exposure.

        Returns
        -------
        ASIExposureStatus
            The status of the exposure."""
        self._assert_handle()
        result, exposure_status = self.asi.get_exposure_status(self.handle)
        self._raise_if_bad(result)
        return ASIExposureStatus(exposure_status)

    def get_exposure_data(self):
        """Gets the exposure data.

        Returns
        -------
        buffer
            The image data."""
        self._assert_handle()
        buffer_size = self.get_image_size()
        buffer = self.asi.get_string_buffer(buffer_size)
        result = self.asi.get_data_after_exposure(self.handle, buffer, buffer_size)
        self._raise_if_bad(result)
        return buffer

    def get_ID(self):
        """Gets the ID of the camera.

        Returns
        -------
        ASIID
            The id of the camera."""
        self._assert_handle()
        result, id = self.asi.get_ID(self.handle)
        self._raise_if_bad(result)
        return id

    def set_ID(self, id):
        """Sets the ID of the camera.

        Parameters
        ----------
        id : ASIIDCtypes
            The new ID of the camera."""
        self._assert_handle()
        result = self.asi.set_ID(self.handle, id)
        self._raise_if_bad(result)

    def get_gain_offsets(self):
        """Gets a set of standard gains and offsets.

        Returns
        -------
        int
            The offset to reach the highest dynamic range.
        int
            The offset for the unity gain.
        int
            The gain for the lowest read noise.
        int
            The offset for the lowest read noise."""
        self._assert_handle()
        (
            result,
            highest_DR_offset,
            unity_gain_offset,
            lowest_RN_gain,
            lowest_RN_offset,
        ) = self.asi.get_gain_offset(self.handle)
        self._raise_if_bad(result)
        return highest_DR_offset, unity_gain_offset, lowest_RN_gain, lowest_RN_offset

    def get_camera_support_modes(self):
        """Gets the supported modes of operations.

        Returns
        -------
        ASISupportedMode
            The modes the camera supports."""
        self._assert_handle()
        result, modes = self.asi.get_camera_support_mode(self.handle)
        self._raise_if_bad(result)
        return modes

    def get_camera_mode(self):
        """Gets the current mode of the camera.

        Returns
        -------
        ASICameraMode
            The current mode of the camera."""
        self._assert_handle()
        result, mode = self.asi.get_camera_mode(self.handle)
        self._raise_if_bad(result)
        return mode

    def set_camera_mode(self, mode: ASICameraMode):
        """Sets the mode of the camera.

        Parameters
        ----------
        mode : ASICameraMode
            The new mode of the camera."""
        self._assert_handle()
        result = self.asi.set_camera_mode(self.handle, mode)
        self._raise_if_bad(result)

    def send_software_trigger(self, start):
        """Sends a software trigger to the camera."""
        self._assert_handle()
        result = self.asi.send_software_trigger(self.handle, self.bool_to_int(start))
        self._raise_if_bad(result)

    def get_serial_number(self):
        """Gets the serial number of the camera."""
        self._assert_handle()
        result, serial_number = self.asi.get_serial_number(self.handle)
        self._raise_if_bad(result)
        return serial_number

    def get_image_size(self):
        """Gets the size of the image based on the current camera configuration
        without taking binning into account.

        Returns
        -------
        int
            The number of bytes per image."""
        width, height, bin, img_type = self.get_ROI()
        bytes_per_pixel = 1
        if img_type == ASIImageType.Raw8:
            bytes_per_pixel = 1
        elif img_type == ASIImageType.RGB24:
            bytes_per_pixel = 3
        elif img_type == ASIImageType.Raw16:
            bytes_per_pixel = 2
        elif img_type == ASIImageType.Y8:
            bytes_per_pixel = 1
        return width * height * bytes_per_pixel

    def bool_to_int(self, value):
        if value:
            return 1
        return 0

    def _assert_handle(self):
        if self.handle == -1:
            raise ASIDeviceNotOpenError()
