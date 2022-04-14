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
        self.dev = self.lib.openASI(self.id)
        self.set_full_frame()

        self.use_zwo_filter_wheel = config.use_zwo_filter_wheel

        self.filter_id = config.filter_id  # ID of the filter wheel not the filter
        self.filter_number = None

        if self.use_zwo_filter_wheel:
            self.zwo_lib = zwofilterwheel.EFWLibrary()
            self.zwo_lib.initialiseLibrary()
            self.zwo_dev = self.zwo_lib.openEFW(self.filter_id)
            # self.zwo_dev.setPosition(self.filter_number)
            self.filter_number = self.zwo_lib.getPosition(self.filter_id)

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
        info = self.dev.getCameraInfo()
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
            self.zwo_dev.setPosition(int(value))
            self.filter_number = int(value)
            while not self.zwo_dev.isInPosition():
                await asyncio.sleep(0.02)
        await super().setValue(key, value)

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
        left, top = self.dev.getStartPosition()
        width, height, binning, imgType = self.dev.getROI()
        return top, left, width, height

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
        print(width, height, self.bin_value, self.current_image_type)
        self.dev.setROI(width, height, self.bin_value, self.current_image_type)
        self.dev.setStartPosition(left, top)

    def set_full_frame(self):
        """Sets the region of interest to the whole sensor."""
        info = self.dev.getCameraInfo()
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
        top, left, width, height = self.getROI()
        self.set_roi(top, left, width, height)
        self.is_live_exposure = True
        super().start_live_view()

    def stop_live_view(self):
        """Configure the camera for a standard exposure."""
        self.current_image_type = self.normal_image_type
        top, left, width, height = self.getROI()
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
        self.dev.setControlValue(
            ASIControlType.Exposure, int(exp_time * 1000000), False
        )
        await super().start_take_image(exp_time, shutter, science, guide, wfs)

    async def start_integration(self):
        """Start integrating."""
        self.dev.startExposure()
        await super().start_integration()

    async def end_integration(self):
        """End integration.

        This should wait for the integration period to complete."""
        result = self.dev.getExposureStatus()
        while result == ASIExposureStatus.Working:
            await asyncio.sleep(0.02)
            result = self.dev.getExposureStatus()
        if result == ASIExposureStatus.Failed:
            raise ASIImageFailed()
        await super().end_integration()

    async def end_readout(self):
        """Start reading out the image."""
        buffer = self.dev.getExposureData()
        buffer_array = np.frombuffer(buffer, dtype=np.uint16)
        exposure_time, auto = self.dev.getControlValue(ASIControlType.Exposure)
        offset, auto = self.dev.getControlValue(ASIControlType.Offset)
        temperature, auto = self.dev.getControlValue(ASIControlType.Temperature)
        cooler_power_percentage, auto = self.dev.getControlValue(
            ASIControlType.CoolerPowerPercentage
        )
        target_temperature, auto = self.dev.getControlValue(
            ASIControlType.TargetTemperature
        )
        cooler_on, auto = self.dev.getControlValue(ASIControlType.CoolerOn)
        top, left, width, height = self.getROI()
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
        videoFormats = []
        for x in info.SupportedVideoFormat:
            if x == -1:
                break
            videoFormats.append(ASIImageType(x))
        self.SupportedVideoFormat = videoFormats
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
        self.intPtr = ctypes.POINTER(ctypes.c_int)
        self.longPtr = ctypes.POINTER(ctypes.c_long)

    def getNumOfConnectedCameras(self):
        # ASICAMERA_API  int ASIGetNumOfConnectedCameras();
        return self.lib.ASIGetNumOfConnectedCameras()

    def getProductIDs(self):
        # ASICAMERA_API int ASIGetProductIDs(int* pPIDs);
        dataType = ctypes.c_int * 256
        productIDs = dataType()
        count = self.lib.ASIGetProductIDs(productIDs)
        return [productIDs[i] for i in range(count)]

    def getCameraProperty(self, index):
        # ASICAMERA_API ASI_ERROR_CODE ASIGetCameraProperty(ASI_CAMERA_INFO
        # *pASICameraInfo, int iCameraIndex);
        cameraProperty = ASICameraInfoCtypes()
        result = self.lib.ASIGetCameraProperty(cameraProperty, index)
        return self._to_result_enum(result), ASICameraInfo(cameraProperty)

    def getCameraPropertyByID(self, id):
        # ASICAMERA_API ASI_ERROR_CODE ASIGetCameraPropertyByID(int iCameraID,
        # ASI_CAMERA_INFO *pASICameraInfo);
        cameraProperty = ASICameraInfoCtypes()
        result = self.lib.ASIGetCameraPropertyByID(id, cameraProperty)
        return self._to_result_enum(result), ASICameraInfo(cameraProperty)

    def openCamera(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIOpenCamera(int iCameraID);
        result = self.lib.ASIOpenCamera(id)
        return self._to_result_enum(result)

    def initCamera(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIInitCamera(int iCameraID);
        result = self.lib.ASIInitCamera(id)
        return self._to_result_enum(result)

    def closeCamera(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASICloseCamera(int iCameraID);
        result = self.lib.ASICloseCamera(id)
        return self._to_result_enum(result)

    def getNumberOfControls(self, id):
        # ASICAMERA_API ASI_ERROR_CODE ASIGetNumOfControls(int iCameraID,
        # int * piNumberOfControls);
        numberOfControls = self._get_int_ptr()
        result = self.lib.ASIGetNumOfControls(id, numberOfControls)
        return self._to_result_enum(result), numberOfControls[0]

    def getControlCaps(self, id, index):
        # ASICAMERA_API ASI_ERROR_CODE ASIGetControlCaps(int iCameraID,
        # int iControlIndex, ASI_CONTROL_CAPS * pControlCaps);
        controlCaps = ASIControlCapsCtypes()
        result = self.lib.ASIGetControlCaps(id, index, controlCaps)
        return self._to_result_enum(result), ASIControlCaps(controlCaps)

    def getControlValue(self, id, controlType):
        # ASICAMERA_API ASI_ERROR_CODE ASIGetControlValue(int  iCameraID,
        # ASI_CONTROL_TYPE  ControlType, long *plValue, ASI_BOOL *pbAuto);
        value = self._get_long_ptr()
        auto = self._get_int_ptr()
        result = self.lib.ASIGetControlValue(id, controlType, value, auto)
        return self._to_result_enum(result), value[0], auto[0]

    def setControlValue(self, id, controlType, value, auto):
        # ASICAMERA_API ASI_ERROR_CODE ASISetControlValue(int  iCameraID,
        # ASI_CONTROL_TYPE  ControlType, long lValue, ASI_BOOL bAuto);
        result = self.lib.ASISetControlValue(id, controlType, value, auto)
        return self._to_result_enum(result)

    def setROIFormat(self, id, width, height, bin, imgType):
        # ASICAMERA_API  ASI_ERROR_CODE ASISetROIFormat(int iCameraID,
        # int iWidth, int iHeight,  int iBin, ASI_IMG_TYPE Img_type);
        result = self.lib.ASISetROIFormat(id, width, height, bin, imgType)
        return self._to_result_enum(result)

    def getROIFormat(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIGetROIFormat(int iCameraID,
        # int *piWidth, int *piHeight,  int *piBin, ASI_IMG_TYPE *pImg_type);
        width = self._get_int_ptr()
        height = self._get_int_ptr()
        bin = self._get_int_ptr()
        imgType = self._get_int_ptr()
        result = self.lib.ASIGetROIFormat(id, width, height, bin, imgType)
        return self._to_result_enum(result), width[0], height[0], bin[0], imgType[0]

    def setStartPosition(self, id, x, y):
        # ASICAMERA_API  ASI_ERROR_CODE ASISetStartPos(int iCameraID, int
        # iStartX, int iStartY);
        result = self.lib.ASISetStartPos(id, x, y)
        return self._to_result_enum(result)

    def getStartPosition(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIGetStartPos(int iCameraID, int
        # *piStartX, int *piStartY);
        x = self._get_int_ptr()
        y = self._get_int_ptr()
        result = self.lib.ASIGetStartPos(id, x, y)
        return self._to_result_enum(result), x[0], y[0]

    def getDroppedFrames(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIGetDroppedFrames(int iCameraID,int
        # *piDropFrames);
        dropFrames = self._get_int_ptr()
        result = self.lib.ASIGetDroppedFrames(id, dropFrames)
        return self._to_result_enum(result), dropFrames[0]

    def enableDarkSubtract(self, id, bmpFile):
        # ASICAMERA_API ASI_ERROR_CODE ASIEnableDarkSubtract(int iCameraID,
        # char *pcBMPPath);
        bmpFilePath = self.get_string_buffer(bmpFile.encode("ascii"))
        result = self.lib.ASIEnableDarkSubtract(id, bmpFilePath)
        return self._to_result_enum(result)

    def disableDarkSubtract(self, id):
        # ASICAMERA_API ASI_ERROR_CODE ASIDisableDarkSubtract(int iCameraID);
        result = self.lib.ASIDisableDarkSubtract(id)
        return self._to_result_enum(result)

    def startVideoCapture(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIStartVideoCapture(int iCameraID);
        result = self.lib.ASIStartVideoCapture(id)
        return self._to_result_enum(result)

    def stopVideoCapture(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIStopVideoCapture(int iCameraID);
        result = self.lib.ASIStopVideoCapture(id)
        return self._to_result_enum(result)

    def getVideoData(self, id, buffer, bufferSize, timeoutMs):
        # ASICAMERA_API  ASI_ERROR_CODE ASIGetVideoData(int iCameraID,
        # unsigned char* pBuffer, long lBuffSize, int iWaitms);
        result = self.lib.ASIGetVideoData(id, buffer, bufferSize, timeoutMs)
        return self._to_result_enum(result)

    def pulseGuideOn(self, id, direction):
        # ASICAMERA_API ASI_ERROR_CODE ASIPulseGuideOn(int iCameraID,
        # ASI_GUIDE_DIRECTION direction);
        result = self.lib.ASIPulseGuideOn(id, direction)
        return self._to_result_enum(result)

    def pulseGuideOff(self, id, direction):
        # ASICAMERA_API ASI_ERROR_CODE ASIPulseGuideOff(int iCameraID,
        # ASI_GUIDE_DIRECTION direction);
        result = self.lib.ASIPulseGuideOff(id, direction)
        return self._to_result_enum(result)

    def startExposure(self, id, isDark):
        # ASICAMERA_API ASI_ERROR_CODE  ASIStartExposure(int iCameraID,
        # ASI_BOOL bIsDark);
        result = self.lib.ASIStartExposure(id, isDark)
        return self._to_result_enum(result)

    def stopExposure(self, id):
        # ASICAMERA_API ASI_ERROR_CODE  ASIStopExposure(int iCameraID);
        result = self.lib.ASIStopExposure(id)
        return self._to_result_enum(result)

    def getExposureStatus(self, id):
        # ASICAMERA_API ASI_ERROR_CODE  ASIGetExpStatus(int iCameraID,
        # ASI_EXPOSURE_STATUS *pExpStatus);
        exposureStatus = self._get_int_ptr()
        result = self.lib.ASIGetExpStatus(id, exposureStatus)
        return self._to_result_enum(result), exposureStatus[0]

    def getDataAfterExposure(self, id, buffer, bufferSize):
        # ASICAMERA_API  ASI_ERROR_CODE ASIGetDataAfterExp(int iCameraID,
        # unsigned char* pBuffer, long lBuffSize);
        result = self.lib.ASIGetDataAfterExp(id, buffer, bufferSize)
        return self._to_result_enum(result)

    def getID(self, id):
        # ASICAMERA_API  ASI_ERROR_CODE ASIGetID(int iCameraID, ASI_ID* pID);
        otherID = ASIIDCtypes()
        result = self.lib.ASIGetID(id, otherID)
        return self._to_result_enum(result), ASIID(otherID)

    def setID(self, id, otherID):
        # ASICAMERA_API  ASI_ERROR_CODE ASISetID(int iCameraID, ASI_ID ID);
        result = self.lib.ASISetID(id, otherID)
        return self._to_result_enum(result)

    def getGainOffset(self, id):
        # ASICAMERA_API ASI_ERROR_CODE ASIGetGainOffset(int iCameraID, int
        # *pOffset_HighestDR, int *pOffset_UnityGain, int *pGain_LowestRN,
        # int *pOffset_LowestRN);
        offsetHighestDR = self._get_int_ptr()
        offsetUnityGain = self._get_int_ptr()
        gainLowestRN = self._get_int_ptr()
        offsetLowestRN = self._get_int_ptr()
        result = self.lib.ASIGetGainOffset(
            id, offsetHighestDR, offsetUnityGain, gainLowestRN, offsetLowestRN
        )
        return (
            self._to_result_enum(result),
            offsetHighestDR[0],
            offsetUnityGain[0],
            gainLowestRN[0],
            offsetLowestRN[0],
        )

    def getSDKVersion(self):
        # ASICAMERA_API char* ASIGetSDKVersion();
        return self.lib.ASIGetSDKVersion().decode("ascii")

    def getCameraSupportMode(self, id):
        # ASICAMERA_API ASI_ERROR_CODE  ASIGetCameraSupportMode(int iCameraID,
        # ASI_SUPPORTED_MODE* pSupportedMode);
        supportedMode = ASISupportedModeCtypes()
        result = self.lib.ASIGetCameraSupportMode(id, supportedMode)
        return self._to_result_enum(result), ASISupportedMode(supportedMode)

    def getCameraMode(self, id):
        # ASICAMERA_API ASI_ERROR_CODE  ASIGetCameraMode(int iCameraID,
        # ASI_CAMERA_MODE* mode);
        mode = self._get_int_ptr()
        result = self.lib.ASIGetCameraMode(id, mode)
        return self._to_result_enum(result), ASICameraMode(mode[0])

    def setCameraMode(self, id, mode):
        # ASICAMERA_API ASI_ERROR_CODE  ASISetCameraMode(int iCameraID,
        # ASI_CAMERA_MODE mode);
        result = self.lib.ASISetCameraMode(id, mode)
        return self._to_result_enum(result)

    def sendSoftwareTrigger(self, id, start):
        # ASICAMERA_API ASI_ERROR_CODE  ASISendSoftTrigger(int iCameraID,
        # ASI_BOOL bStart);
        result = self.lib.ASISendSoftTrigger(id, start)
        return self._to_result_enum(result)

    def getSerialNumber(self, id):
        # ASICAMERA_API ASI_ERROR_CODE  ASIGetSerialNumber(int iCameraID,
        # ASI_SN* pSN);
        serialNumber = ASIIDCtypes()
        result = self.lib.ASIGetSerialNumber(id, serialNumber)
        return self._to_result_enum(result), ASIID(serialNumber)

    def _get_int_ptr(self, defaultValue=0):
        return self.intPtr(ctypes.c_int(defaultValue))

    def _get_long_ptr(self, defaultValue=0):
        return self.longPtr(ctypes.c_long(defaultValue))

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

    def _raiseIfBad(self, result: Results):
        if result != Results.Success:
            raise ASIError(result)


class ASILibrary(ASIBase):
    def __init__(self, asi=None):
        super().__init__(asi)
        self.initialised = False

    def initialise(self):
        """Initialise the ASICamera2 Library."""
        if not self.initialised:
            self.asi.getNumOfConnectedCameras()
            self.initialised = True

    def getDeviceCount(self):
        """Gets the number of ASI cameras attached to this machine.

        Returns
        -------
        int
            The number of cameras attached to this machine."""
        self._assertInitialised()
        deviceCount = self.asi.getNumOfConnectedCameras()
        return deviceCount

    def getProductIDs(self):
        """Gets the product IDs of all the ASI cameras attached to this
        machine.

        Returns
        -------
        int list
            The product IDs of the cameras attached to this machine."""
        self._assertInitialised()
        productIDs = self.asi.getProductIDs()
        return productIDs

    def getCameraInfo(self, index):
        """Gets camera information for the ASI camera at the specified index.

        Parameters
        ----------
        index : int
            The index of the camera (0, getDeviceCount()).

        Returns
        -------
        ASICameraInfo
            The camera information."""
        self._assertInitialised()
        result, cameraInfo = self.asi.getCameraProperty(index)
        self._raiseIfBad(result)
        return cameraInfo

    def getSDKVersion(self):
        """Gets the SDK version for the library.

        Returns
        -------
        str
            The version of the SDK."""
        self._assertInitialised()
        return self.asi.getSDKVersion()

    def openASI(self, index):
        """Opens the specified ASI camera attached to this machine.

        Parameters
        ----------
        index : int
            The index (0 to getDeviceCount()) of the camera to open.

        Returns
        -------
        ASIDevice
            The camera device."""
        self._assertInitialised()
        device = ASIDevice(index, self.asi)
        return device

    def _assertInitialised(self):
        if not self.initialised:
            raise ASILibraryNotInitialised()


class ASIDevice(ASIBase):
    def __init__(self, index, asi=None):
        super().__init__(asi)
        self.handle = -1
        result = self.asi.openCamera(index)
        self._raiseIfBad(result)
        result = self.asi.initCamera(index)
        self.handle = index

    def close(self):
        """Closes this device."""
        self._assert_handle()
        result = self.asi.closeCamera(self.handle)
        self._raiseIfBad(result)
        self.handle = -1

    def getCameraInfo(self):
        """Gets camera information for this ASI camera.

        Returns
        -------
        ASICameraInfo
            The camera information."""
        self._assert_handle()
        result, cameraInfo = self.asi.getCameraPropertyByID(self.handle)
        self._raiseIfBad(result)
        return cameraInfo

    def getNumberOfControls(self):
        """Gets the number of controls available for this ASI camera.

        Returns
        -------
        int
            The number of controls available."""
        self._assert_handle()
        result, controlCount = self.asi.getNumberOfControls(self.handle)
        self._raiseIfBad(result)
        return controlCount

    def getControlInfo(self, index):
        """Gets the information on the control at the specified index.

        Parameters
        ----------
        index : int
            The index of the control (0, getNumberOfControls()).

        Returns
        -------
        ASIControlCaps
            The information on the specified control."""
        self._assert_handle()
        result, controlInfo = self.asi.getControlCaps(self.handle, index)
        self._raiseIfBad(result)
        return controlInfo

    def getControlValue(self, controlType: ASIControlType):
        """Gets the value of the specified control.

        Parameters
        ----------
        controlType : ASIControlType
            The control to query.

        Returns
        -------
        int
            The value of the control.
        bool
            True if the control is set to auto."""
        self._assert_handle()
        result, value, auto = self.asi.getControlValue(self.handle, controlType.value)
        self._raiseIfBad(result)
        return value, auto

    def setControlValue(self, controlType: ASIControlType, value, auto: bool):
        """Sets the value of the specified control.

        Parameters
        ----------
        controlType : ASIControlType
            The control to set.
        value : int
            The new value of the control.
        auto : bool
            True if the control should be set automatically."""
        self._assert_handle()
        result = self.asi.setControlValue(
            self.handle, controlType.value, value, self.bool_to_int(auto)
        )
        self._raiseIfBad(result)

    def setROI(self, width, height, bin, imgType: ASIImageType):
        """Sets the region of interest, binning, and image type.

        Parameters
        ----------
        width : int
            The width of the region.
        height : int
            The height of the region.
        bin : int
            The bin size for the region.
        imgType : ASIImageType
            The image format."""
        self._assert_handle()
        result = self.asi.setROIFormat(self.handle, width, height, bin, imgType.value)
        self._raiseIfBad(result)

    def getROI(self):
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
        result, width, height, bin, imgType = self.asi.getROIFormat(self.handle)
        self._raiseIfBad(result)
        return width, height, bin, ASIImageType(imgType)

    def setStartPosition(self, x, y):
        """Sets the start position of the region of interest.

        Parameters
        ----------
        x : int
            The x position.
        y : int
            The y position."""
        self._assert_handle()
        result = self.asi.setStartPosition(self.handle, x, y)
        self._raiseIfBad(result)

    def getStartPosition(self):
        """Gets the start position of the region of interest.

        Returns
        -------
        int
            The x position.
        int
            The y position."""
        self._assert_handle()
        result, x, y = self.asi.getStartPosition(self.handle)
        self._raiseIfBad(result)
        return x, y

    def getDroppedFrames(self):
        """Gets the number of frames dropped by the camera.

        Returns
        -------
        int
            The number of dropped frames."""
        self._assert_handle()
        result, droppedFrames = self.asi.getDroppedFrames(self.handle)
        self._raiseIfBad(result)
        return droppedFrames

    def enableDarkSubtract(self, pathToBMP):
        """Enables the camera to automatically subtract a dark frame.

        Parameters
        ----------
        pathToBMP : str
            The path to the dark image as a bitmap."""
        self._assert_handle()
        result = self.asi.enableDarkSubtract(self.handle, pathToBMP)
        self._raiseIfBad(result)

    def disableDarkSubtract(self):
        """Disables the automatic subtraction of a dark frame."""
        self._assert_handle()
        result = self.asi.disableDarkSubtract(self.handle)
        self._raiseIfBad(result)

    def startVideoCapture(self):
        """Starts capturing video."""
        self._assert_handle()
        result = self.asi.startVideoCapture(self.handle)
        self._raiseIfBad(result)

    def stopVideoCapture(self):
        """Stops capturing video."""
        self._assert_handle()
        result = self.asi.stopVideoCapture(self.handle)
        self._raiseIfBad(result)

    def getVideoData(self):
        """Gets video data.

        Returns
        -------
        buffer
            The image data."""
        self._assert_handle()
        bufferSize = self.get_image_size()
        buffer = self.asi.get_string_buffer(bufferSize)
        exposure_time_in_us = self.getControlValue(ASIControlType.Exposure)
        timeoutInMs = int((exposure_time_in_us * 2 + 500000) / 1000)
        result = self.asi.getVideoData(self.handle, buffer, bufferSize, timeoutInMs)
        self._raiseIfBad(result)
        return buffer

    def pulseGuideOn(self, direction: ASIGuideDirection):
        """Issues a guide pulse on the ST4 port for the
        specified direction.

        Parameters
        ----------
        direction : ASIGuideDirection
            The direction to start the pulse."""
        self._assert_handle()
        result = self.asi.pulseGuideOn(self.handle, direction.value)
        self._raiseIfBad(result)

    def pulseGuideOff(self, direction: ASIGuideDirection):
        """Stops issuing a guide pulse on the ST4 port for the
        specified direction.

        Parameters
        ----------
        direction : ASIGuideDirection
            The direction to start the pulse."""
        self._assert_handle()
        result = self.asi.pulseGuideOff(self.handle, direction.value)
        self._raiseIfBad(result)

    def startExposure(self, isDark=False):
        """Starts an exposure.

        Parameters
        ----------
        isDark : bool (optional)
            If true uses the mechanical shutter to take a dark (if available).
        """
        self._assert_handle()
        result = self.asi.startExposure(self.handle, self.bool_to_int(isDark))
        self._raiseIfBad(result)

    def stopExposure(self):
        """Stops an exposure."""
        self._assert_handle()
        result = self.asi.stopExposure(self.handle)
        self._raiseIfBad(result)

    def getExposureStatus(self):
        """Gets the status of a currently running exposure.

        Returns
        -------
        ASIExposureStatus
            The status of the exposure."""
        self._assert_handle()
        result, exposureStatus = self.asi.getExposureStatus(self.handle)
        self._raiseIfBad(result)
        return ASIExposureStatus(exposureStatus)

    def getExposureData(self):
        """Gets the exposure data.

        Returns
        -------
        buffer
            The image data."""
        self._assert_handle()
        bufferSize = self.get_image_size()
        buffer = self.asi.get_string_buffer(bufferSize)
        result = self.asi.getDataAfterExposure(self.handle, buffer, bufferSize)
        self._raiseIfBad(result)
        return buffer

    def getID(self):
        """Gets the ID of the camera.

        Returns
        -------
        ASIID
            The id of the camera."""
        self._assert_handle()
        result, id = self.asi.getID(self.handle)
        self._raiseIfBad(result)
        return id

    def setID(self, id):
        """Sets the ID of the camera.

        Parameters
        ----------
        id : ASIIDCtypes
            The new ID of the camera."""
        self._assert_handle()
        result = self.asi.setID(self.handle, id)
        self._raiseIfBad(result)

    def getGainOffsets(self):
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
            highestDROffset,
            unityGainOffset,
            lowestRNGain,
            lowestRNOffset,
        ) = self.asi.getGainOffset(self.handle)
        self._raiseIfBad(result)
        return highestDROffset, unityGainOffset, lowestRNGain, lowestRNOffset

    def getCameraSupportModes(self):
        """Gets the supported modes of operations.

        Returns
        -------
        ASISupportedMode
            The modes the camera supports."""
        self._assert_handle()
        result, modes = self.asi.getCameraSupportMode(self.handle)
        self._raiseIfBad(result)
        return modes

    def getCameraMode(self):
        """Gets the current mode of the camera.

        Returns
        -------
        ASICameraMode
            The current mode of the camera."""
        self._assert_handle()
        result, mode = self.asi.getCameraMode(self.handle)
        self._raiseIfBad(result)
        return mode

    def setCameraMode(self, mode: ASICameraMode):
        """Sets the mode of the camera.

        Parameters
        ----------
        mode : ASICameraMode
            The new mode of the camera."""
        self._assert_handle()
        result = self.asi.setCameraMode(self.handle, mode)
        self._raiseIfBad(result)

    def sendSoftwareTrigger(self, start):
        """Sends a software trigger to the camera."""
        self._assert_handle()
        result = self.asi.sendSoftwareTrigger(self.handle, self.bool_to_int(start))
        self._raiseIfBad(result)

    def getSerialNumber(self):
        """Gets the serial number of the camera."""
        self._assert_handle()
        result, serialNumber = self.asi.getSerialNumber(self.handle)
        self._raiseIfBad(result)
        return serialNumber

    def get_image_size(self):
        """Gets the size of the image based on the current camera configuration
        without taking binning into account.

        Returns
        -------
        int
            The number of bytes per image."""
        width, height, bin, imgType = self.getROI()
        bytesPerPixel = 1
        if imgType == ASIImageType.Raw8:
            bytesPerPixel = 1
        elif imgType == ASIImageType.RGB24:
            bytesPerPixel = 3
        elif imgType == ASIImageType.Raw16:
            bytesPerPixel = 2
        elif imgType == ASIImageType.Y8:
            bytesPerPixel = 1
        return width * height * bytesPerPixel

    def bool_to_int(self, value):
        if value:
            return 1
        return 0

    def _assert_handle(self):
        if self.handle == -1:
            raise ASIDeviceNotOpenError()
