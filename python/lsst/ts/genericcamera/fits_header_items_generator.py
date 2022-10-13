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
    "FitsHeaderItemsFromHeaderYaml",
    "FitsHeaderItemsGenerator",
    "FitsHeaderItem",
]

from collections import defaultdict
import pathlib

import yaml


class FitsHeaderItem:
    """Convenience class for storing FITS Header items.."""

    def __init__(self, name, value, comment=""):
        """Construct a FitsHeaderItem.

        Parameters
        ----------
        name: `str`
            The name of the FITS header item.
        value: Any
            The value of the FITS header item.
        comment: `str`, optional
            The comment of the FITS header item, or '' which gets ignored by
            astropy.
        """
        self.name = name
        self.value = value
        self.comment = comment

    def __repr__(self):
        return (
            f"FitsHeaderItem(name={self.name}, "
            f"value={self.value}, "
            f"comment={self.comment})"
        )

    def __call__(self):
        return (self.name, self.value, self.comment)


class FitsHeaderItemsGenerator:
    """Convenience class for generating FitsHeaderItem instances."""

    def __init__(self):
        """Construct a FitsHeaderItemsGenerator."""

    def generate_fits_header_items(self):
        """Generate and return a dict of name: FitsHeaderItem.

        Returns
        -------
        fits_header_items: `list`
            A fixed list of `FitsHeaderItem`.
        """
        fits_header_items = []
        fits_header_items.append(
            FitsHeaderItem("TIMESYS", "TAI", "The time scale used")
        )
        fits_header_items.append(
            FitsHeaderItem("DATE", None, "Creation Date and Time of File")
        )
        fits_header_items.append(
            FitsHeaderItem("DATE-OBS", None, "Date of observation (image acquisition)")
        )
        fits_header_items.append(
            FitsHeaderItem("DATE-BEG", None, "Time at the start of integration")
        )
        fits_header_items.append(
            FitsHeaderItem("DATE-END", None, "Time at the start of readout")
        )
        fits_header_items.append(
            FitsHeaderItem("EXPTIME", None, "Exposure time in seconds")
        )
        return fits_header_items


class FitsHeaderItemsFromHeaderYaml:
    """Convert Header Service YAML file into FitsHeaderItems

    Attributes
    ----------
    ignore_list: `dict`
        The set of header keywords to ignore from the YAML file.
    header_items: `dict`
        The set of header items generated from the YAML file.
    """

    ignore_list = {
        "PRIMARY": ["SIMPLE", "BITPIX", "NAXIS", "EXTEND"],
        "IMAGE1": ["XTENSION", "BITPIX", "PCOUNT", "GCOUNT"],
    }

    def __init__(self, header_file: pathlib.Path) -> None:
        """Construct the FitsHeaderFromHeaderYaml object.

        Parameters
        ----------
        header_file: `pathlib.Path`
            The header file to convert into the FITS header items.
        """
        with header_file.open() as ifile:
            header_info = yaml.safe_load(ifile)

        self.header_items = defaultdict(list)

        for key, header_set in header_info.items():
            for keyword_dict in header_set:
                keyword = keyword_dict["keyword"]
                if keyword in self.ignore_list[key]:
                    continue
                if keyword == "COMMENT":
                    self.header_items[key].append(FitsHeaderItem("", "", ""))
                elif keyword is None:
                    self.header_items[key].append(
                        FitsHeaderItem(
                            "", self._fixup_value(keyword_dict["comment"]), ""
                        )
                    )
                else:
                    self.header_items[key].append(
                        FitsHeaderItem(
                            keyword.strip(),
                            self._fixup_value(keyword_dict["value"]),
                            keyword_dict["comment"].strip(),
                        )
                    )

    def _fixup_value(self, value):
        """Fix up issues with a header value for a keyword.

        Parameters
        ----------
        value: Any
            The header value for fix up.

        Returns
        -------
        keyword_value: Any
            The fix up value for the given keyword.
        """
        try:
            keyword_value = value.strip().replace("'", "")
        except AttributeError:
            if value is None:
                keyword_value = ""
            else:
                keyword_value = value
        return keyword_value
