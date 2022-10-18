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
import warnings

from .basecamera import *

try:
    from .alliedvisioncamera import *
except ImportError as e:
    warnings.warn(f"AlliedVision driver is not available: {e.args[0]}.")

from .andorcamera import *

try:
    from .canoncamera import *
except ImportError as e:
    warnings.warn(f"CanonCamera driver is not available: {e.args[0]}.")

from .simulatorcamera import *
from .zwocamera import *
from .zwofilterwheel import *
