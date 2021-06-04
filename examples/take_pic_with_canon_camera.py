import io
import logging
import os

from lsst.ts.GenericCamera import exposure

import gphoto2 as gp
import numpy as np
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
exposure = exposure.Exposure(luminance, width, height, tags, isJPEG=False)
exposure.save(os.path.join("", "img.fits"))

logging.info("Done image.")
camera.exit()
