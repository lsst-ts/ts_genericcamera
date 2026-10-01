# This file is part of ts_genericcamera.
#
# Developed for the Vera C. Rubin Observatory Telescope and Site Systems.
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import io
import logging
import os

import gphoto2 as gp
import numpy as np
from lsst.ts.genericcamera import exposure
from rawpy import RawPy

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
    level=logging.INFO,
)

width = 6744
height = 4502
exposure_time = 1
iso = 200

context = None
camera = gp.Camera()
camera.init()
cfg = camera.get_config()
cfg.get_child_by_name("imageformat").set_value("RAW")
cfg.get_child_by_name("shutterspeed").set_value(str(exposure_time))
cfg.get_child_by_name("focusmode").set_value("Manual")
cfg.get_child_by_name("picturestyle").set_value("Standard")
cfg.get_child_by_name("iso").set_value(str(iso))

camera.set_config(cfg, None)

logging.info("Taking image.")
file_path = camera.capture(gp.GP_CAPTURE_IMAGE)
logging.info("Camera file path: {file_path.folder}{file_path.name}")
logging.info("Downloading image.")
camera_file = camera.file_get(file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL)
camera_file.save(file_path.name)
file_data = camera_file.get_data_and_size()
logging.info("Saving image.")
raw = RawPy()
raw.open_buffer(io.BytesIO(file_data))
raw.unpack()
rgb = raw.postprocess(
    no_auto_bright=True, use_auto_wb=False, gamma=(1, 1), output_bps=16
)
logging.info(f"Size of rgb image: {rgb.shape}")
# Use luminosity conversion to get 16 bit B/W image. See
# https://stackoverflow.com/a/51571053
luminance = np.dot(rgb[..., :3], [0.299, 0.587, 0.114])
logging.info(f"Size of bw image: {luminance.shape}")
logging.info("Removing image from camera.")
del camera_file
raw.close()
# Set up the tags for the exposure. Unfortunately no temperature data
# are available with this camera.
tags = {
    "TOP": 0,
    "LEFT": 0,
    "WIDTH": width,
    "HEIGHT": height,
    "EXPOSURE": exposure_time,
    "ISO": iso,
}
exposure = exposure.Exposure(luminance, width, height, tags, False)
exposure.save(os.path.join("", "img.fits"))

logging.info("Done image.")
camera.exit()
