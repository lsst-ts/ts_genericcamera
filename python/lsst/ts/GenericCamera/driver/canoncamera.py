# This file is part of ts_GenericCamera.
#
# Developed for the LSST Telescope and Site Systems.
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

import io

from .. import exposure
from . import genericcamera

import gphoto2 as gp
import numpy as np
from PIL import Image


class CanonCamera(genericcamera.GenericCamera):
    def __init__(self, log=None):
        super().__init__(log=log)
        self.id = None
        self.binValue = None
        self.normalImageType = None
        self.currentImageType = None
        self.width = None
        self.height = None
        self.camera = None
        self.exposure_time = None

        # The path to the image in the camera
        self.file_path = None

    @staticmethod
    def name():
        """Set camera name."""
        return "Canon"

    def initialise(self, config):
        """Initialise the camera with the specified configuration file.

        Parameters
        ----------
        config : str
            The name of the configuration file to load."""
        self.id = config.id
        self.binValue = config.binValue
        self.normalImageType = config.ImageType
        self.currentImageType = self.normalImageType
        self.width = config.width
        self.height = config.height

        # Initialize the camera. If not camera is detected then an Exception
        # will be raised.
        self.camera = gp.Camera()
        self.camera.init()

    def getMakeAndModel(self):
        """Get the make and model of the camera.

        Returns
        -------
        str
            The make and model of the camera."""
        abilities = self.camera.get_abilities()
        return abilities.model

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
        return 0, 0, self.width, self.height

    async def startTakeImage(self, expTime, shutter, science, guide, wfs):
        """Start taking an image or a set of images.

        Parameters
        ----------
        expTime : float
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
        # Store the exposure time for later use
        self.exposure_time = expTime
        # In order to be able to update the cameraq config via GPhoto, the
        # config object needs to be obtained ...
        cfg = self.camera.get_config()
        # ... the config parameters need to be adjusted ...
        imageformat = cfg.get_child_by_name("imageformat")
        imageformat.set_value("Large Fine JPEG")
        eosremoterelease = cfg.get_child_by_name("eosremoterelease")
        eosremoterelease.set_value("Immediate")
        cancelautofocus = cfg.get_child_by_name("cancelautofocus")
        cancelautofocus.set_value(0)
        capturetarget = cfg.get_child_by_name("capturetarget")
        capturetarget.set_value("Internal RAM")
        shutterspeed = cfg.get_child_by_name("shutterspeed")
        shutterspeed.set_value(str(expTime))
        # ... and the config needs to be written baqck to the camera
        self.camera.set_config(cfg, None)
        await super().startTakeImage(expTime, shutter, science, guide, wfs)

    async def startIntegration(self):
        """Start integrating."""
        # This starts the exposure while obtaining the path to the file on the
        # camera. The exposure will finish by itself because the camera
        # controls that.
        self.file_path = self.camera.capture(gp.GP_CAPTURE_IMAGE)
        await super().startIntegration()

    async def endReadout(self):
        """End reading out the image."""
        # The image can be obtained by reading out the file_path variable in
        # which the path to the file on the camera was stored.
        camera_file = self.camera.file_get(self.file_path.folder, self.file_path.name, gp.GP_FILE_TYPE_NORMAL)
        # Load the image data
        file_data = camera_file.get_data_and_size()
        # Convert to a numpy array
        image = Image.open(io.BytesIO(file_data))
        buffer = image.tobytes()
        buffer_array = np.frombuffer(buffer, dtype=np.uint16)
        # Set up the tags for the exposure. The temperature can be read from
        # the exif data but I don't have that working yet because it involves
        # more native libraries to be installed.
        tags = {
            "TOP": 0,
            "LEFT": 0,
            "WIDTH": self.width,
            "HEIGHT": self.height,
            "EXPOSURE": (self.exposure_time / 1000000.0),
            "OFFSET": 0,
            "TEMPERATURE": -99,
            "COOLER_POWER_PERCENTAGE": 0,
            "TARGET_TEMPERATURE": -99,
            "COOLER_ON": False,
        }
        image = exposure.Exposure(buffer_array, self.width, self.height, tags)
        return image
