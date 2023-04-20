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

import io

import numpy as np
from astropy.io import fits
from PIL import Image


class Exposure:
    """This class is used to define an exposure. It provides methods
    for manipulating an exposure and saving it to the local disk."""

    def __init__(
        self, buffer, width, height, tags, header=None, dtype=np.uint16, is_jpeg=False
    ):
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
        header: `dict`
            A set of key/value pairs containing image information.
        dtype : dtype (optional)
            Type of image data.
        is_jpeg : bool (optional)
            True if the image described is a JPEG.
        """
        self.width = width
        self.height = height
        self.buffer = buffer.reshape(height, width)
        self.tags = tags
        self.header = header
        self.is_jpeg = is_jpeg
        self.dtype = dtype

    @property
    def suffix(self):
        """Provide a file suffix"""
        return ".jpeg" if self.is_jpeg else ".fits"

    def make_fileobj(self):
        """Create an object suitable for saving to a file.

        Returns
        -------
        fileobj: `io.BytesIO`
        """
        if self.is_jpeg:
            fileobj = io.BytesIO(self.buffer)
        else:
            img = fits.ImageHDU(self.buffer)
            hdul = fits.HDUList([fits.PrimaryHDU(), img])
            hdr_primary = hdul[0].header
            hdr_image1 = hdul[1].header
            if self.header is not None:
                for item in self.header["PRIMARY"]:
                    hdr_primary.append(item(), end=True)
                for item in self.header["IMAGE1"]:
                    hdr_image1.append(item(), end=True)
            else:
                for tag in self.tags:
                    hdr_primary.append((tag.name, tag.value, tag.comment), end=True)
            fileobj = io.BytesIO()
            hdul.writeto(fileobj)
            fileobj.seek(0)

        return fileobj

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
        fileobj = self.make_fileobj()

        if self.is_jpeg:
            img = Image.open(fileobj)
            img.save(file_path, "jpeg")
        else:
            with open(file_path, "wb") as ofile:
                ofile.write(fileobj.getbuffer())
