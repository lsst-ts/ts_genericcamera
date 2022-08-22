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

__all__ = ["DATE_FORMAT", "DATETIME_FORMAT", "get_dayobs"]

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
