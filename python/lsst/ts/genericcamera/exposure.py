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

__all__ = ["Exposure"]

from astropy.io import fits
import io
import numpy as np
from PIL import Image


class Exposure:
    """This class is used to define an exposure. It provides methods
    for manipulating an exposure and saving it to the local disk."""

    def __init__(self, buffer, width, height, tags, dtype=np.uint16, is_jpeg=False):
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
        tags : list
            A list of FitsHeaderItem tags that describe the image.
        dtype : dtype (optional)
            Type of image data.
        is_jpeg : bool (optional)
            True if the image described is a JPEG.
        """
        self.width = width
        self.height = height
        print(len(buffer))
        self.buffer = buffer.reshape(height, width)
        self.tags = tags
        self.is_jpeg = is_jpeg
        self.dtype = dtype

    def make_jpeg(self):
        """Takes this exposure and converts it to a JPEG."""
        # fileMemory = io.BytesIO()
        # img = Image.frombuffer('L', (self.width, self.height), self.buffer)
        # # The following call takes the most time
        # # If performing optimization, this is a good choice
        # img.save(fileMemory, 'jpeg')
        #
        # self.buffer = np.array(fileMemory.getbuffer())
        # fileMemory.close()

        self.buffer = self.buffer.astype(np.uint8)

        self.is_jpeg = True
        self.dtype = self.buffer.dtype

    def save(self, file_path):
        """Saves this exposure to the local drive.

        Parameters
        ----------
        file_path : str
            The path to the file to save the image to."""

        if self.is_jpeg:
            img = Image.open(io.BytesIO(self.buffer))
            img.save(file_path, "jpeg")
        else:
            img = fits.PrimaryHDU(self.buffer)
            hdul = fits.HDUList([img])
            hdr = hdul[0].header
            for tag in self.tags:
                hdr.append((tag.name, tag.value, tag.comment), end=True)
            hdul.writeto(file_path)
