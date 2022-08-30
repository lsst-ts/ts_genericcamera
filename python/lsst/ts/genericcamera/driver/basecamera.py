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

__all__ = ["BaseCamera"]

import abc
import ctypes
import logging

from astropy.coordinates import Angle, SkyCoord
from astropy.time import Time
from astropy import units as u

from lsst.ts import utils

from .. import exposure
from ..fits_header_items_generator import FitsHeaderItemsGenerator, FitsHeaderTemplate


class BaseCamera(abc.ABC):
    """This class describes the methods required by a generic camera."""

    def __init__(self, log=None):
        if log is None:
            self.log = logging.getLogger(__name__)
        else:
            self.log = log

        # Load the generic FITS header items.
        fhig = FitsHeaderItemsGenerator()
        self.tags = fhig.generate_fits_header_items(FitsHeaderTemplate.ALL_SKY)

        # Variables holding image acquisition info
        self.timestamp_end_integration = None
        self.timestamp_start_readout = None
        self.timestamp_end_readout = None

    @staticmethod
    @abc.abstractmethod
    def name():
        """Set camera name."""
        raise NotImplementedError()

    def initialise(self, config):
        """Initialise the camera with the specified configuration file.

        Parameters
        ----------
        config : str
            The name of the configuration file to load."""
        pass

    @abc.abstractmethod
    def get_config_schema(self):
        """Get the configuration schema for this GenericCamera Model.

        Returns
        -------
        `dict`
            The configuration schema in yaml format.
        """
        raise NotImplementedError()

    @property
    def datetime_end_integration(self):
        """Object representation of the end integration timestamp."""
        return Time(self.timestamp_end_integration, scale="tai", format="unix_tai")

    @property
    def datetime_start_readout(self):
        """Object representation of the start readout timestamp."""
        return Time(self.timestamp_start_readout, scale="tai", format="unix_tai")

    @property
    def datetime_end_readout(self):
        """Object representation of the end readout timestamp."""
        return Time(self.timestamp_end_readout, scale="tai", format="unix_tai")

    async def stop(self):
        """Stop and close camera."""
        pass

    def get_make_and_model(self):
        """Get the make and model of the camera.

        Returns
        -------
        str
            The make and model of the camera."""
        return "GenericCamera"

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
        return "UNDEFINED"

    async def set_value(self, key, value):
        """Set a unique property of the camera.

        Parameters
        ----------
        key : str
            The name of the property.
        value : str
            The value of the property."""
        pass

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
        return 0, 0, 0, 0

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
        pass

    def set_full_frame(self):
        """Sets the region of interest to the whole sensor."""
        pass

    def start_live_view(self):
        """Starts a live view data stream from the camera.

        This should change the image format to 8bits per pixel so
        the image can be encoded to JPEG."""
        pass

    def stop_live_view(self):
        """Stops an active live view data stream from the camera.

        This should review the image format back to 16bits per pixel."""
        pass

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
        self.timestamp_start_readout = utils.current_tai()
        return True

    async def start_shutter_open(self):
        """Start opening the shutter.

        If the camera doesn't have a shutter then don't do anything."""
        pass

    async def end_shutter_open(self):
        """End opening the shutter.

        If the camera does have a shutter then this should wait for the
        shutter to finish opening.

        If the camera doesn't have a shutter then don't do anything."""
        pass

    async def start_integration(self):
        """Start integrating."""
        pass

    async def end_integration(self):
        """End integration.

        This should wait for the integration period to complete."""
        self.timestamp_end_integration = utils.current_tai()

    async def start_shutter_close(self):
        """Start closing the shutter.

        If the camera does have a shutter then start closing the
        shutter.

        If the camera doesn't have a shutter then don't do anything."""
        pass

    async def end_shutter_close(self):
        """End closing the shutter.

        If the camera does have a shutter then this should wait for
        the shutter to finishing closing.

        If the camera doesn't have a shutter then don't do anything."""
        pass

    async def start_readout(self):
        """Start reading out the image."""
        self.timestamp_end_readout = utils.current_tai()

    async def end_readout(self):
        """End reading out the image.

        Returns
        -------
        exposure.Exposure
            The exposure."""
        return exposure.Exposure(ctypes.create_string_buffer(0), 1, 1, {})

    async def end_take_image(self):
        """End take image or images."""
        pass

    def get_tag(self, name):
        """Convenience function to retrieve the FITS header tag with the
        provided name.

        Parameters
        ----------
        name: `str`
            The name of the tag to return.

        Returns
        -------
        tag: FitsHeaderItem or None
            Returns the FitsHeaderItem with the provided name, or None if it
            doesn't exist.
        """
        try:
            # Each tag should only exist once.
            fhi = [tag for tag in self.tags if tag.name == name][0]
        except IndexError:
            # If no tag is found then returen None.
            fhi = None
        return fhi

    def get_static_configuration_for_key_value_map(self) -> str | None:
        """Provide camera specific configuration to the key-value map.

        Returns
        -------
        `str` or `None`
            Static camera configuration in the format of
            key1: value1, key2: value2 ...
        """
        return None

    async def _get_radec_from_altaz_location_time(self, alt, az, obs_time, location):
        """Get the Right Ascension and Declination from the altitude and
        azimuth for the given time and location.

        Parameters
        ----------
        alt: `float`
            The altitude in degrees.
        az: `float`
            The azimuth in degrees.
        obs_time: `str`
            A string representing the date and time. Valid strings are those
            accepted by astropy.
        location: `astropy.coordinates.EarthLocation`
            The EarthLocation representing the longitude, latitude and
            elevation of the location.

        Returns
        -------
        ra_dec: `astropy.coordinates.SkyCoord`
            The SkyCoord representing the Right Ascension and Declination.
        """
        time = Time(obs_time, scale="utc")
        altaz = SkyCoord(
            alt=Angle(alt * u.deg),
            az=Angle(az * u.deg),
            frame="altaz",
            obstime=time,
            location=location,
        )
        ra_dec = altaz.transform_to("icrs")
        return ra_dec
