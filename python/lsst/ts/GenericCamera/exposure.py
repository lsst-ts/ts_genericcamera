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

import astropy.io
import ctypes
import io
import struct
import numpy as np
import time
from PIL import Image


class Exposure():
    """This class is used to define an exposure. It provides methods
    for manipulating an exposure and saving it to the local disk."""
    def __init__(self, buffer, width, height, tags, isJPEG=False):
        """Constructs an exposure object.

        Exposures meant to be a JPEG image should have 8bit pixels.
        Exposures meant to be a FITS image should have 16bit pixels.

        Parameters
        ----------
        buffer : buffer
            The buffer containing the image data.
        width : int
            The width of the image.
        height : int
            The height of the image.
        tags : map
            A list of tags that describe the image.
        isJPEG : bool (optional)
            True if the image described is a JPEG."""
        self.buffer = buffer
        self.width = width
        self.height = height
        self.tags = tags
        self.isJPEG = isJPEG

    def makeJPEG(self):
        """Takes this exposure and converts it to a JPEG.
        """
        fileMemory = io.BytesIO()
        img = Image.frombuffer('L', (self.width, self.height), self.buffer)
        # The following call takes the most time
        # If performing optimization, this is a good choice
        img.save(fileMemory, 'jpeg')
        self.buffer = np.array(fileMemory.getbuffer())
        fileMemory.close()
        self.isJPEG = True

    def save(self, filePath):
        """Saves this exposure to the local drive.
        
        Parameters
        ----------
        filePath : str
            The path to the file to save the image to."""
        if self.isJPEG:
            img = Image.open(io.BytesIO(self.buffer))
            img.save(filePath, 'jpeg')
        else:
            try:
                count = int(self.width * self.height)
                ints = struct.unpack('H'*count, self.buffer)
                pixels = np.asarray(ints)
                imgPix = np.reshape(pixels, (self.height, self.width))
                imgPix = imgPix.astype(np.uint16)
                img = astropy.io.fits.PrimaryHDU(imgPix)
                hdul = astropy.io.fits.HDUList([img])
                hdr = hdul[0].header
                # for key in self.tags:
                #     hdr[key] = self.tags[key]
                hdul.writeto(filePath)
            except:
                print(f"Failed to save image to file {filePath}.")
