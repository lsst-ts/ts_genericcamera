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
    "FitsHeaderTemplate",
    "HEADERS_DIR",
]

from collections import defaultdict
from enum import Enum
import pathlib

import yaml

HEADERS_DIR = pathlib.Path(__file__).resolve().parents[0] / "headers"
"""The directory in which the header files reside."""


class FitsHeaderTemplate(Enum):
    """Enumeration of all available FITS header templates."""

    ALL_SKY = "allsky"
    CANON = "canon"
    STARTRACKER = "startracker"


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

    def generate_fits_header_items(self, fits_header_template):
        """Read the header file and return a dict of name: FitsHeaderItem.

        Parameters
        ----------
        fits_header_template: `FitsHeaderTemplate`
            The name of the header file to open.

        Returns
        -------
        fits_header_items: `list`
            A list of FitsHeaderItem generated from the lines in the header
            file.
        """
        fits_header_items = []
        filename = HEADERS_DIR / f"{fits_header_template.value}.header"
        with open(filename) as f:
            for line in f:
                item_string = line.strip()
                fhi = self._generate_fits_header_item(item_string)
                fits_header_items.append(fhi)
        return fits_header_items

    def _generate_fits_header_item(self, item_string):
        """Take a FITS header item string and generate a FitsHeaderItem
        instance from the values in the string.

        Parameters
        ----------
        item_string: `str`
            The FITS header item string representation.

        Notes
        -----
        A FITS header item string can take several forms. These forms are

          '': An empty line which should result in an empty name, value and
          comment.
          some_value: A line not containing an '=' not a '/' symbol. These are
          comment lines which should result in an empty name and comment and a
          value containing the contents of the comment line with all leading
          and trailing white space and all single quotes stripped.
          some_name = some_value: A line containing an '=' and not a '/'
          symbol. These are header (name, value) tuples that should result in
          an empty commant, a name containing the header name and a value
          containing the header value of the comment line with all leading and
          trailing white space stripped.
          some_name = some_value / some_comment: A line containing an '=' and a
          '/' symbol. These are header (name, value, comment) tuples that
          should result in a name containing the header name, a value
          containing the header value and a comment containing the header
          comment of the comment line with all leading and trailing white space
          stripped.

        Type conversion from string to int or float is done automatically by
        astropy.
        """
        item_string = item_string
        name = ""
        value = ""
        comment = ""

        if item_string != "":

            if "=" not in item_string:
                # A comment line is always a string
                value = item_string
            else:
                name_and_rest = item_string.split("=")
                name = name_and_rest[0]
                rest = name_and_rest[1]
                if "/" not in rest:
                    value = rest
                else:
                    value_and_comment = rest.split("/")
                    value = value_and_comment[0]
                    # Make sure that units like [arcsen/pix] are treated
                    # correctly.
                    comment = "/".join(value_and_comment[1:])

        name = name.strip()
        # Remove any single quotes since they will be added again by astropy.
        value = value.strip().replace("'", "")
        comment = comment.strip()
        return FitsHeaderItem(name, value, comment)


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
