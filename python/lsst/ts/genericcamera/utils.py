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

__all__ = [
    "DATE_FORMAT",
    "DATETIME_FORMAT",
    "get_dayobs",
    "make_image_names",
    "parse_key_value_map",
]

from astropy.time import Time, TimeDelta


DATE_FORMAT = "%Y-%m-%d"
"""Format string for date values in the FITS header."""

DATETIME_FORMAT = f"{DATE_FORMAT}T%H:%M:%S"
"""Format string for datetime values in the FITS header."""


def get_dayobs(timestamp: float) -> str:
    """Get the DAYOBS for the given timestamp.

    Parameters
    ----------
    timestamp: `float`
        The timestamp to derive the DAYOBS. Scale is assumed to be UTC.

    Returns
    -------
    dayobs: `str`
        The calculated DAYOBS.
    """
    time_obj = Time(timestamp, scale="utc", format="unix")
    dayobs_time = time_obj - TimeDelta(12 * 3600, format="sec")
    return dayobs_time.strftime("%Y%m%d")


def make_image_names(gctag: str, dayobs: str, seqnums: list[int]) -> list[str]:
    """Create a list of image service type image names.

    Parameters
    ----------
    gctag: `str`
        The tag name for the indexed GenericCamera.
    dayobs: `str`
        The DAYOBS for the images.
    seqnums: `list`
        The list of sequence numbers to generate image names for.

    Returns
    -------
    image_names: `list`
        The list of image service type image names.
    """
    image_names = []
    for i in seqnums:
        image_names.append(f"{gctag}_O_{dayobs}_{i:06d}")
    return image_names


def parse_key_value_map(kvm: str) -> (str, str):
    """Create keys and values string from key-value map.

    Parameters
    ----------
    kvm: `str`
        The key-value map parse.

    Returns
    -------
    keys: `str`
        The set of keys from the map.
    values: `str`
        The set of values from the map.
    """
    parts = kvm.split(",")
    keys_list = []
    values_list = []

    for part in parts:
        try:
            k, v = part.split(":")
        except ValueError:
            # The value has colons in it.
            index = part.find(":")
            k = part[:index]
            v = part[index + 1 :]
            v = v.replace(":", r"\:")
        keys_list.append(k.strip())
        values_list.append(v.strip())

    return ":".join(keys_list), ":".join(values_list)
