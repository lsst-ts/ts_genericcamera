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

__all__ = ["GenericCameraCsc", "requests", "run_genericcamera"]

import asyncio
import inspect
import logging
import pathlib
import traceback
import types
import typing

import numpy as np
import requests
import yaml
from astropy.time import Time
from lsst.ts import salobj, utils
from requests.exceptions import ConnectionError

from . import __version__, driver
from .config_schema import CONFIG_SCHEMA
from .fits_header_items_generator import FitsHeaderItemsFromHeaderYaml
from .liveview import liveview
from .utils import get_day_obs, make_image_names, parse_key_value_map

LV_ERROR = 1000
"""Error code for when the live view loop dies and the CSC is in enable
state.
"""

AE_ERROR = 2000
"""Error code for when the auto exposure loop dies and the CSC is in
enable state.
"""

DEFAULT_SHUTTER_TIME = 1
"""The assumed total shutter open and close time (seconds) for calculating the
IN_PROGRESS ack timeout."""

DEFAULT_READOUT_TIME = 1
"""The assumed readout time (seconds) for calculating the IN_PROGRESS ack
timeout."""


def run_genericcamera():
    asyncio.run(GenericCameraCsc.amain(index=True))


class GenericCameraCsc(salobj.ConfigurableCsc):
    valid_simulation_modes = (0,)
    version = __version__

    def __init__(
        self,
        index,
        config_dir=None,
        initial_state=salobj.State.STANDBY,
        simulation_mode=0,
    ):
        super().__init__(
            "GenericCamera",
            index=index,
            config_schema=CONFIG_SCHEMA,
            config_dir=config_dir,
            initial_state=initial_state,
            simulation_mode=simulation_mode,
        )

        ch = logging.StreamHandler()
        console_format = (
            "%(asctime)s - %(levelname)s - %(name)s [%(filename)s:%(lineno)d]: "
            "%(message)s"
        )
        ch.setFormatter(logging.Formatter(console_format))
        self.log.addHandler(ch)

        # Create dictionary of camera options.
        self.drivers = {}
        for member in inspect.getmembers(driver):
            is_class = inspect.isclass(member[1])
            is_subclass = (
                False if not is_class else issubclass(member[1], driver.BaseCamera)
            )
            not_gencam = member[1] is not driver.BaseCamera
            if is_class and is_subclass and not_gencam:
                self.drivers[member[1].name()] = member[1]

        self.ip = None
        self.port = None
        self._directory = pathlib.Path.home() / "data"
        self.directory = pathlib.Path.home() / "data"
        self.file_name_format = "{timestamp}-{index}-{total}"
        self.config = None

        self.camera = None
        self.server = None

        self.image_source = f"GC{index}"
        # GenericCameras can only be run by the OCS
        self.image_controller = "O"

        self.day_obs = None
        self.image_sequence_num = 1
        self.image_service_url = None
        self.require_image_service = False
        self.additional_keys = None
        self.additional_values = None

        self.is_live = False
        self.is_auto_exposure = False
        self.is_exposing = False
        self.run_live_task = False
        self.live_task = None
        self.run_auto_exposure_task = False
        self.auto_exposure_task = None

        self.use_lfa = False
        self.always_save = True

        self.s3bucket = None
        self.s3bucket_name = None
        self.s3_mock = False

        self.header_service_remote = salobj.Remote(
            self.domain,
            "GCHeaderService",
            index,
            include=["largeFileObjectAvailable"],
            evt_max_history=0,
        )
        self.header_service_remote.evt_largeFileObjectAvailable.flush()
        self.header_service_remote.evt_largeFileObjectAvailable.callback = (
            self.gc_header_service_large_file_object_available_callback
        )
        self.header_file_dict = {}

        self.log.debug("Generic Camera CSC Ready")

    async def start(self):
        await super().start()
        await self.header_service_remote.start_task

    async def begin_enable(self, data):
        """Begin do_enable; called before state changes.

        This method will start the liveview server and initialize the camera
        with the configuration sent during start.

        Parameters
        ----------
        data : `CommandIdData`
            Command ID and data
        """
        self.server = liveview.LiveViewServer(self.config.port, log=self.log)
        if self.s3bucket is None and self.use_lfa:
            self.s3bucket = salobj.AsyncS3Bucket(
                name=self.s3bucket_name, domock=self.s3_mock, create=self.s3_mock
            )

    async def begin_disable(self, data):
        """Begin do_disable; called before state changes.

        The method will check if the camera is exposing and reject the command
        in case an exposure is in course.

        Parameters
        ----------
        data : `CommandIdData`
            Command ID and data
        """
        if self.is_exposing:
            raise RuntimeError("Camera is exposing, cannot disable.")

    async def end_disable(self, data):
        """End do_disable; called after state changes but before command
        acknowledged.

        The method will stop any live view, close live view server and
        remove the S3 bucket handle.

        Parameters
        ----------
        data : `CommandIdData`
            Command ID and data
        """
        if self.is_live:
            try:
                self.run_live_task = False
                await self.live_task
                self.camera.stop_live_view()
            except Exception as e:
                self.log.error("Exception while stopping live task.")
                self.log.exception(e)

        if self.server is not None:
            try:
                await self.server.stop()
            except Exception as e:
                self.log.error("Exception while closing live view image server.")
                self.log.exception(e)
            finally:
                self.server = None

        if self.s3bucket is not None:
            self.s3bucket.stop_mock()
        self.s3bucket = None
        self.log.info("end_disable")

    async def begin_standby(self, data):
        """Begin do_standby; called before the state changes.

        This method will stop the camera.

        Parameters
        ----------
        data : `DataType`
            Command data
        """
        if self.camera is not None:
            try:
                await self.camera.stop()
            except Exception as e:
                self.log.error("Exception while stopping camera.")
                self.log.exception(e)
            finally:
                self.camera = None

    async def do_setValue(self, data):
        """Set a parameter/value pair.

        Parameters
        ----------
        data :
            id : `int`
                The command id.
            data : `GenericCamera_command_setValueC`
                parametersAndValues : `str`
                    A comma deliminated pair key,value.
        """
        self.assert_enabled("setValue")
        self._assert_notlive()

        self.log.info("setValue - Start")
        tokens = data.parametersAndValues.split(",")
        await self.camera.set_value(tokens[0], tokens[1])
        self.log.info("setValue - End")

    async def do_setROI(self, data):
        """Set the region of interest.

        Parameters
        ----------
        data :
            id : `int`
                The command id.
            data : `GenericCamera_command_setROIC`
                topPixel : `int`
                    The top pixel of the RIO in binned pixels.
                leftPixel : `int`
                    The left pixel of the RIO in binned pixels.
                width : `int`
                    The width of the ROI in binned pixels.
                height : `int`
                    The height of the ROI in binned pixels.
        """
        self.assert_enabled("setROI")
        self._assert_notlive()

        self.log.debug("setROI - Start")
        self.camera.set_roi(data.topPixel, data.leftPixel, data.width, data.height)
        await self.evt_roi.set_write(
            topPixel=data.topPixel,
            leftPixel=data.leftPixel,
            width=data.width,
            height=data.height,
            force_output=True,
        )
        self.log.debug("setROI - End")

    async def do_setFullFrame(self, data):
        """Set the region of interest to full frame.

        Parameters
        ----------
        data :
            id : `int`
                The command id.
            data : `GenericCamera_command_setFullFrameC`
                ignored : bool
                    This is ignored.
        """
        self.log.info("setFullFrame - Start")
        self.assert_enabled("setFullFrame")
        self._assert_notlive()
        self.camera.set_full_frame()
        top, left, width, height = self.camera.get_roi()
        await self.evt_roi.set_write(
            topPixel=top, leftPixel=left, width=width, height=height, force_output=True
        )
        self.log.info("setFullFrame - End")

    async def do_startLiveView(self, data):
        """Starts the live view display.

        Parameters
        ----------
        data :
            id : int
                The command id.
            data : GenericCamera_command_startLiveViewC
                expTime : float
                    The exposure time for the live view."""
        self.assert_enabled("startLiveView")
        self.log.info("startLiveView - Start")
        self._assert_notlive()
        self._assert_notautoexposure()
        if data.expTime == 0.0:
            raise RuntimeError("LiveView exposure time must be greater than zero.")
        self.camera.start_live_view()
        self.run_live_task = True
        await asyncio.wait_for(self.server.start(), timeout=2)
        self.live_task = asyncio.ensure_future(self.live_view_loop(data.expTime))
        await self.evt_startLiveView.set_write(ip=self.ip, port=self.port)
        self.log.info("startLiveView - End")

    async def do_stopLiveView(self, data):
        """Stop the live view display.

        Parameters
        ----------
        data :
            id : `int`
                The command id.
            data : `GenericCamera_command_stopLiveViewC`
                ignored : `bool`
                    This is ignored.
        """
        self.assert_enabled("stopLiveView")
        self._assert_live()

        self.log.info("stopLiveView - Start")

        self.run_live_task = False
        await self.live_task

        await self.stop_liveview()

        self.log.info("stopLiveView - End")

    async def stop_liveview(self):
        """Stop live view."""

        try:
            await self.server.stop()
        except Exception as e:
            self.log.error("Exception trying to stop liveview.")
            self.log.exception(e)

        try:
            self.camera.stop_live_view()
        except Exception as e:
            self.log.error("Exception trying to stop liveview.")
            self.log.exception(e)

        await self.evt_endLiveView.write()

    async def do_takeImages(self, data):
        """Start taking images.

        Parameters
        ----------
        data :
            id : `int`
                The command id.
            data : `GenericCamera_command_takeImagesC`
                numImages : `int`
                    The number of images to take in the sequence.
                expTime : `float`
                    The exposure time in seconds.
                shutter : `bool`
                    True if the shutter should be utilized.
        """
        self.assert_enabled("takeImages")
        self._assert_notlive()
        self._assert_notautoexposure()
        self.is_exposing = True

        try:
            self.log.info("takeImages - Start")
            images_in_sequence = data.numImages
            exposure_time = data.expTime
            time_stamp = utils.current_tai()

            image_names, image_sequence_array = self.get_image_names_from_image_service(
                images_in_sequence, time_stamp
            )

            self.parse_key_value_map(data.keyValueMap)

            # Calculate expected time for IN_PROGRESS ack
            total_shutter_time = (
                images_in_sequence * DEFAULT_SHUTTER_TIME if data.shutter else 0
            )
            total_exposure_time = images_in_sequence * exposure_time
            total_readout_time = images_in_sequence * DEFAULT_READOUT_TIME
            expected_timeout = (
                total_exposure_time + total_shutter_time + total_readout_time
            )
            self.log.debug(f"In progress timeout: {expected_timeout} seconds")

            await self.cmd_takeImages.ack_in_progress(
                data=data, timeout=expected_timeout
            )

            await self.evt_startTakeImage.write()

            for image_index in range(images_in_sequence):
                self.image_sequence_num = image_sequence_array[image_index]
                image_name = image_names[image_index]
                await self.camera.start_take_image(
                    exposure_time,
                    data.shutter,
                    data.sensors,
                    data.keyValueMap,
                    data.obsNote,
                )
                exposure = await self.take_image(
                    shutter=data.shutter,
                    images_in_sequence=images_in_sequence,
                    image_index=image_index,
                    exposure_time=exposure_time,
                    timestamp=time_stamp,
                    image_name=image_name,
                )
                await self.camera.end_take_image()
                await self.handle_exposure_saving(exposure, time_stamp, image_name)

            await self.evt_endTakeImage.write()
            # Adjust SEQNUM in case web service is unavailable
            self.image_sequence_num += 1
        except Exception as e:
            self.log.exception(e)
            raise e
        finally:
            self.is_exposing = False
        self.log.info("takeImages - End")

    async def do_startStreamingMode(self, data) -> None:
        """Starts streaming mode on the camera."""
        # TODO: Implement (SITCOM-774)
        raise NotImplementedError("startStreaming mode not implemented (SITCOM-774)!")

    async def do_stopStreamingMode(self, _) -> None:
        """Stop streaming mode on the camera."""
        # TODO: Implement (SITCOM-774)
        raise NotImplementedError("stopStreamingMode not implemented (SITCOM-774)!")

    def parse_key_value_map(self, key_value_map: str) -> None:
        """Parse key/value map into additional keys and values.

        Add extra information from the camera if necessary.

        Parameters
        ----------
        key_value_map: `str`
            The key/value map to parse.
        """
        try:
            new_keyValueMap = ", ".join(
                [
                    key_value_map,
                    self.camera.get_configuration_for_key_value_map(),
                ]
            )
        except TypeError:
            new_keyValueMap = key_value_map

        self.log.debug(f"Final key/value map: {new_keyValueMap}")

        self.additional_keys, self.additional_values = parse_key_value_map(
            new_keyValueMap
        )

    def get_image_names_from_image_service(
        self, num_images: int, timestamp: float
    ) -> typing.Tuple[list[str], list[int]]:
        """Get image names and sequence numbers from image service.

        If the image service is not available, the code will generate the
        required information from internal state.

        Parameters
        ----------
        num_images: `int`
            The number of images to request names for.
        timestamp: `float`
            The timestamp used in case the service isn't available.

        Returns
        -------
        image_names: `list`
            The set of image names returned from the service.
        image_sequence_array: `list`
            The set of SEQNUMs for the requested images.
        """
        try:
            response = requests.get(
                self.image_service_url,
                params={"n": num_images, "sourceIndex": self.salinfo.index},
            )
            if response.status_code == 200:
                json_response = response.json()
                self.day_obs = json_response[0].split("_")[2]
                image_sequence_array = [int(x.split("_")[-1]) for x in json_response]
                image_names = json_response
            else:
                self.log.warning(
                    f"Image name service returned an error: {response.status_code}"
                )
                if self.require_image_service:
                    raise ConnectionError(
                        f"Image name service returned an error: {response.status_code}"
                    )
                image_sequence_array = self._get_day_obs_and_seq_num_array(
                    timestamp, num_images
                )
                image_names = make_image_names(
                    self.image_source, self.day_obs, image_sequence_array
                )
        except ConnectionError:
            self.log.exception("Cannot connect to image name service.")
            if self.require_image_service:
                raise
            image_sequence_array = self._get_day_obs_and_seq_num_array(
                timestamp, num_images
            )
            image_names = make_image_names(
                self.image_source, self.day_obs, image_sequence_array
            )
        return image_names, image_sequence_array

    async def gc_header_service_large_file_object_available_callback(self, lfoa):
        """Handle callback when receiving a LFOA event from GCHeaderService.

        Parameters
        ----------
        lfoa: `salobj.DataType`
        """
        result = requests.get(lfoa.url)
        header_filename = lfoa.url.split("/")[-1]
        header_file = self.directory / header_filename
        with header_file.open("w") as ofile:
            ofile.write(result.content.decode())
        file_stem = header_file.stem
        header_tag = "_".join(file_stem.split("_")[2:])
        self.header_file_dict[header_tag] = header_file

    async def handle_exposure_saving(self, exposure, timestamp, image_name):
        """Save exposure to LFA or local directory.

        Parameters
        ----------
        exposure: `lsst.ts.genericcamera.Exposure`
            The exposure to save.
        timestamp: `float`
            The timestamp for the exposure.
        image_name: `str`
            The filename for the exposure.
        """
        try:
            header_info = None
            try:
                header_file = self.header_file_dict[image_name]
                fhifhy = FitsHeaderItemsFromHeaderYaml(header_file)
                header_info = fhifhy.header_items
                del self.header_file_dict[image_name]
                header_file.unlink(missing_ok=True)
            except KeyError:
                self.log.warning(f"Cannot find image {image_name} in lookup.")
            exposure.header = header_info
        except ValueError:
            self.log.warning(f"No header for image {image_name} found.")

        filename = f"{image_name}{exposure.suffix}"

        if self.use_lfa:
            self.log.debug("Writing file to LFA.")
            key = self.s3bucket.make_key(
                salname=self.salinfo.name,
                salindexname=None,
                generator=str(self.salinfo.index),
                other=image_name,
                date=Time(timestamp, scale="tai", format="unix_tai"),
                suffix=exposure.suffix,
            )
            # Make image name more like bigger cameras
            key = key[: key.rfind("/") + 1] + f"{image_name}{exposure.suffix}"
            filename = key

            await self.s3bucket.upload(fileobj=exposure.make_fileobj(), key=key)

            url = f"{self.s3bucket.service_resource.meta.client.meta.endpoint_url}/{self.s3bucket.name}/{key}"

            await self.evt_largeFileObjectAvailable.set_write(
                url=url, generator=f"{self.salinfo.name}:{self.salinfo.index}"
            )

        if self.always_save or not self.use_lfa:
            output_file = self.directory / filename
            if not output_file.parents[0].exists():
                self.log.debug(f"Creating directory: {output_file.parents[0]}")
                output_file.parents[0].mkdir(parents=True)
            self.log.debug(f"Saving file to disk: {output_file}")
            exposure.save(output_file)

    async def take_image(
        self,
        shutter,
        images_in_sequence,
        image_index,
        exposure_time,
        timestamp,
        image_name,
    ):
        """Take a single image with the given parameters.

        Parameters
        ----------
        shutter: `bool`
            True if the shutter should be utilized.
        images_in_sequence: `int`
            The number of images to take in the sequence.
        image_index: `int`
            The index of the image in the sequence.
        exposure_time: `float`
            The exposure time in seconds.
        timestamp: `float`
            The time in seconds.
        image_name: `str`
            The name of the image file.
        Returns
        -------
        exposure: `exposure.Exposure`
            The exposure.
        """
        if shutter:
            await self.evt_startShutterOpen.write()
            await self.camera.start_shutter_open()

            await self.camera.end_shutter_open()
            await self.evt_endShutterOpen.write()

        # Put start integration timestamp closer to call
        # This value is used later in the other events (endIntegration,
        # startReadout and endReadout) so we need to keep it for those.
        timestamp = utils.current_tai()
        await self.evt_startIntegration.set_write(
            imagesInSequence=images_in_sequence,
            imageName=image_name,
            imageIndex=image_index,
            timestampAcquisitionStart=timestamp,
            exposureTime=exposure_time,
            imageSource=self.image_source,
            imageController=self.image_controller,
            imageNumber=self.image_sequence_num,
            imageDate=self.day_obs,
            additionalKeys=self.additional_keys,
            additionalValues=self.additional_values,
        )
        await self.camera.start_integration()
        await self.camera.end_integration()
        await self.evt_endIntegration.set_write(
            additionalKeys=self.additional_keys,
            additionalValues=self.additional_values,
            timestampAcquisitionEnd=self.camera.timestamp_end_integration,
        )

        if shutter:
            await self.evt_startShutterClose.write()
            await self.camera.start_shutter_close()

            await self.camera.end_shutter_close()
            await self.evt_endShutterClose.write()
        await self.evt_startReadout.set_write(
            imagesInSequence=images_in_sequence,
            imageName=image_name,
            imageIndex=image_index,
            timestampAcquisitionStart=timestamp,
            timestampStartOfReadout=utils.current_tai(),
            exposureTime=exposure_time,
            imageSource=self.image_source,
            imageController=self.image_controller,
            imageNumber=self.image_sequence_num,
            imageDate=self.day_obs,
            additionalKeys=self.additional_keys,
            additionalValues=self.additional_values,
        )
        await self.camera.start_readout()

        exposure = await self.camera.end_readout()
        await self.evt_endReadout.set_write(
            imagesInSequence=images_in_sequence,
            imageName=image_name,
            imageIndex=image_index,
            timestampAcquisitionStart=timestamp,
            timestampEndOfReadout=self.camera.timestamp_end_readout,
            requestedExposureTime=exposure_time,
            imageSource=self.image_source,
            imageController=self.image_controller,
            imageNumber=self.image_sequence_num,
            imageDate=self.day_obs,
            additionalKeys=self.additional_keys,
            additionalValues=self.additional_values,
        )
        return exposure

    async def do_startAutoExposure(self, data):
        """Start taking exposures automatically.

        Parameters
        ----------
        data :
            minExpTime : `float`
                The minimum exposure time in seconds.
            maxExpTime : `float`
                The maximum exposure time in seconds.
            configuration : `str`
                A Yaml string containing additional configuration
                parameters.
        """
        self.assert_enabled("startAutoExposure")
        self.log.info("startAutoExposure - Start")
        self._assert_notlive()
        self._assert_notautoexposure()
        self.run_auto_exposure_task = True

        # Prepare potential configuration items for the loop
        configuration = {
            "shutter": False,
            "sensors": "",
            "keyValueMap": "",
            "obsNote": "",
        }
        if data.configuration != "":
            loaded_configuration = yaml.safe_load(data.configuration)
            for key in configuration:
                if key in loaded_configuration:
                    configuration[key] = loaded_configuration[key]

        self.parse_key_value_map(configuration["keyValueMap"])

        self.auto_exposure_task = asyncio.ensure_future(
            self.run_auto_exposure_loop(data.minExpTime, data.maxExpTime, configuration)
        )
        await self.evt_autoExposureStarted.set_write(
            minExpTime=data.minExpTime,
            maxExpTime=data.maxExpTime,
            configuration=data.configuration,
        )
        self.log.info("startAutoExposure - End")

    async def do_stopAutoExposure(self, data):
        """Stop taking exposures automatically.

        Parameters
        ----------
        data
            Nothing passed on.
        """
        self.assert_enabled("stopAutoExposure")
        self._assert_autoexposure()

        self.log.info("stopAutoExposure - Start")

        self.run_auto_exposure_task = False
        await self.auto_exposure_task

        await self.stop_auto_exposure()

        self.log.info("stopAutoExposure - End")

    async def stop_auto_exposure(self):
        """Stop auto exposure.

        Not much content for now but this may change in the future.
        """

        await self.evt_autoExposureStopped.write()

    async def live_view_loop(self, exposure_time):
        """Run the live view capture loop.

        Parameters
        ----------
        exposure_time : `float`
            The exposure time of the image (in seconds).
        """
        self.log.debug("live_view_loop - Start")
        self.is_live = True
        try:
            while self.run_live_task:
                await self.camera.start_take_image(
                    exposure_time, True, True, True, True
                )

                start_frame_time = utils.current_tai()

                self.log.debug("start shutter open")
                await self.camera.start_shutter_open()
                self.log.debug("end shutter open")
                await self.camera.end_shutter_open()
                self.log.debug("start integration")
                await self.camera.start_integration()
                self.log.debug("end integration")
                await self.camera.end_integration()
                self.log.debug("start_shutter_close")
                await self.camera.start_shutter_close()
                self.log.debug("end_shutter_close")
                await self.camera.end_shutter_close()
                self.log.debug("start_readout")
                await self.camera.start_readout()
                self.log.debug("end_readout")
                exposure = await self.camera.end_readout()
                self.log.debug("end_take_image")
                await self.camera.end_take_image()
                exposure.make_jpeg()
                self.log.debug(f"{exposure.buffer}")
                await self.server.send_exposure(exposure)
                stop_frame_time = utils.current_tai()
                frame_time = round(stop_frame_time - start_frame_time, 3)
                self.log.debug(f"live_view_loop - {frame_time}")
        except Exception as e:
            self.log.error("Error in live view loop.")
            self.log.exception(e)
            await self.stop_liveview()

            await self.fault(
                code=LV_ERROR,
                report="Error in live view loop.",
                traceback=traceback.format_exc(),
            )

        self.is_live = False
        self.log.info("live_view_loop - End")

    async def run_auto_exposure_loop(self, min_exp_time, max_exp_time, configuration):
        """Prepare and start the auto exposure capture loop.

        The cadence of the images is determined by the value of
        config.auto_exposure_nterval.

        Parameters
        ----------
        min_exp_time: `float`
            The minimum exposure time to use.
        max_exp_time: `float`
            The maximum exposure time to use.
        configuration: `dict`
            A dict containing additional configuration parameters.
        """
        self.log.info("autoExposure_loop - Start")
        self.is_auto_exposure = True

        augmented_configuration = configuration.copy()
        augmented_configuration["images_in_sequence"] = 0
        augmented_configuration["image_index"] = 0
        augmented_configuration["exposure_time"] = min_exp_time

        try:
            await self.run_auto_exposure(
                min_exp_time, max_exp_time, augmented_configuration
            )
        except Exception:
            self.log.exception("Error in auto exposure loop.")
            await self.stop_auto_exposure()

            await self.fault(
                code=AE_ERROR,
                report="Error in auto exposure loop.",
                traceback=traceback.format_exc(),
            )

        self.is_auto_exposure = False
        self.log.info("autoExposure_loop - End")

    async def run_auto_exposure(self, min_exp_time, max_exp_time, configuration):
        """Take auto exposures until `run_auto_exposure_task` is False.

        Parameters
        ----------
        min_exp_time: `float`
            The minimum exposure time to use.
        max_exp_time: `float`
            The maximum exposure time to use.
        configuration: `dict`
            A dict containing additional configuration parameters.
        """

        # First determine the exposure time based by taking images
        # starting from the configured minimum exposure time.
        timestamp = utils.current_tai()
        temp_image_name = self.file_name_format.format(
            timestamp=int(timestamp), index=0, total=1
        )
        exposure_time_auto_current = await self.determine_exposure_time(
            min_exp_time, max_exp_time, configuration, timestamp, temp_image_name
        )

        self.log.debug(
            f"Initial auto exposure time: {exposure_time_auto_current}s "
            f"[{min_exp_time}:{max_exp_time}]"
        )

        # Then loop and take images using the latest exposure time and
        # update the exposure time if necessary on the way.
        while self.run_auto_exposure_task:
            timestamp = utils.current_tai()
            image_names, image_sequence_array = self.get_image_names_from_image_service(
                configuration["images_in_sequence"], timestamp
            )
            image_index = configuration["image_index"]
            self.image_sequence_num = image_sequence_array[image_index]
            image_name = image_names[image_index]

            await self.evt_startTakeImage.write()
            await self.camera.start_take_image(
                exposure_time_auto_current,
                configuration["shutter"],
                configuration["sensors"],
                configuration["keyValueMap"],
                configuration["obsNote"],
            )

            # Create a sleep task to wait for while taking the image.
            task_timer = asyncio.create_task(
                asyncio.sleep(self.config.auto_exposure_interval)
            )
            # Take an exposure until the background level is within
            # the expected boundaries. This updates the exposure time
            # as well.
            (
                exposure,
                exposure_time_auto_new,
            ) = await self.get_auto_exposure_and_exposure_time(
                min_exp_time,
                max_exp_time,
                configuration,
                timestamp,
                image_name,
                exposure_time_auto_current,
            )

            if exposure:
                # Save the image.
                await self.handle_exposure_saving(exposure, timestamp, image_name)
                # Update the initial exposure time for the next run of
                # the loop.
                self.log.debug(
                    f"Auto exposure time adjusted: {exposure_time_auto_current}s "
                    f"-> {exposure_time_auto_new}s."
                )
                exposure_time_auto_current = exposure_time_auto_new

            await self.camera.end_take_image()
            await self.evt_endTakeImage.write()

            # Now await the sleep task so either taking images is done
            # or a new one gets scheduled.
            await task_timer

    async def determine_exposure_time(
        self,
        min_exp_time,
        max_exp_time,
        configuration,
        timestamp,
        image_name,
    ):
        """Take images starting with the configured minimum exposure
        time and increasing it up to the maximum exposure time if
        necessary while determining the background level and verify
        it that is within the configured limits.

        Parameters
        ----------
        min_exp_time: `float`
            The minimum exposure time to use.
        max_exp_time: `float`
            The maximum exposure time to use.
        configuration: `dict`
            A dict containing configuration parameters.
        timestamp: `float`
            The timestamp of the exposure [s].
        image_name: `str`
            The name of the exposure file.

        Returns
        -------
        exposure_time: `float`
            The exposure time determined by inspecting the background
            level of images taken with varying exposure times.
        """
        exposure_time = configuration["exposure_time"]

        await self.camera.start_take_image(
            exposure_time,
            configuration["shutter"],
            configuration["sensors"],
            configuration["keyValueMap"],
            configuration["obsNote"],
        )

        background_level = 0.0
        while not (
            self.config.min_background <= background_level <= self.config.max_background
        ):
            self.log.debug("Taking exposure.")
            exposure = await self.take_image(
                configuration["shutter"],
                configuration["images_in_sequence"],
                configuration["image_index"],
                exposure_time,
                timestamp,
                image_name,
            )
            self.log.debug("Establishing exposure background level.")
            background_level = self.establish_exposure_background(exposure)
            self.log.debug(
                f"Background level is {background_level} and a value between "
                f"{self.config.min_background} and {self.config.max_background} "
                f"is expected."
            )
            new_exposure_time = await self.adjust_exposure_time(
                min_exp_time,
                max_exp_time,
                configuration,
                background_level,
                exposure_time,
            )

            if (
                not (
                    self.config.min_background
                    <= background_level
                    <= self.config.max_background
                )
                and new_exposure_time == exposure_time
            ):
                self.log.warn(
                    "Cannot take an exposure with a valid background level. Ignoring."
                )
                break

            exposure_time = new_exposure_time

        return exposure_time

    async def get_auto_exposure_and_exposure_time(
        self,
        min_exp_time,
        max_exp_time,
        configuration,
        timestamp,
        image_name,
        initial_exposure_time,
    ):
        """Take exposures and adjust the exposure time if necessary
        based on the background level of the image.

        Parameters
        ----------
        min_exp_time: `float`
            The minimum exposure time to use.
        max_exp_time: `float`
            The maximum exposure time to use.
        configuration: `dict`
            A dict containing additional configuration parameters.
        timestamp: `float`
            The timestamp of the exposure [s].
        image_name: `str`
            The name of the exposure file.
        initial_exposure_time: `float`
            The initial exposure time [s]

        Returns
        -------
        exposure: `exposure.Exposure`
            An exposure with a background level between the configured
            minimum and maximim exposure times.
        exposure_time: `float`
            The exposure time to use by the next run of the loop.
        """
        exposure = None
        exposure_time = initial_exposure_time

        self.log.debug("Taking exposure.")
        exposure = await self.take_image(
            configuration["shutter"],
            configuration["images_in_sequence"],
            configuration["image_index"],
            exposure_time,
            timestamp,
            image_name,
        )
        self.log.debug("Establishing exposure background level.")
        background_level = self.establish_exposure_background(exposure)
        self.log.debug(
            f"Background level is {background_level} and a value between "
            f"{self.config.min_background} and {self.config.max_background} "
            f"is expected."
        )
        new_exposure_time = await self.adjust_exposure_time(
            min_exp_time,
            max_exp_time,
            configuration,
            background_level,
            exposure_time,
        )

        exposure_time = new_exposure_time
        return exposure, exposure_time

    async def adjust_exposure_time(
        self, min_exp_time, max_exp_time, configuration, background_level, exposure_time
    ):
        """Adjust the exposure time based on the current exposure time
        and the background level.

        Parameters
        ----------
        min_exp_time: `float`
            The minimum exposure time to use.
        max_exp_time: `float`
            The maximum exposure time to use.
        configuration: `dict`
            A dict containing additional configuration parameters.
        background_level: `float`
            The background level to compare against the background
            level limits.
        exposure_time: `float`
            The current exposure time [s].

        Returns
        -------
        new_exposure_time: `float`
            The new exposure time based on the background level and
            the current exposure time.
        """
        new_exposure_time = exposure_time
        if background_level > self.config.max_background:
            new_exposure_time = exposure_time / 2.0
            if new_exposure_time < min_exp_time:
                new_exposure_time = min_exp_time
        elif background_level < self.config.min_background:
            new_exposure_time = exposure_time * 2.0
            if new_exposure_time > max_exp_time:
                new_exposure_time = max_exp_time
        return new_exposure_time

    def establish_exposure_background(self, exposure):
        background_level = np.median(exposure.buffer)
        return background_level

    @staticmethod
    def get_config_pkg():
        return "ts_config_ocs"

    async def configure(self, config):
        """Configure the CSC.

        Parameters
        ----------
        config : `object`
            The configuration as described by the schema at ``schema_path``,
            as a struct-like object.

        Notes
        -----
        Called when running the ``start`` command, just before changing
        summary state from `State.STANDBY` to `State.DISABLED`.
        """

        self.directory = (
            pathlib.Path(config.directory)
            if config.directory is not None
            else self._directory
        )

        if not self.directory.exists():
            raise RuntimeError(f"Directory {self.directory} does not exist.")

        for instance in config.instances:
            if instance["sal_index"] == self.salinfo.index:
                break
        else:
            raise salobj.ExpectedError(
                f"No config found for sal_index={self.salinfo.index}"
            )

        self.use_lfa = config.s3instance is not None
        self.always_save = config.always_save

        self.s3_mock = config.s3instance == "mock"

        self.log.info(
            f"s3 instance: {config.s3instance} -> use_lfa: {self.use_lfa}, s3_mock: {self.s3_mock}"
        )

        if self.use_lfa:
            self.s3bucket_name = salobj.AsyncS3Bucket.make_bucket_name(
                s3instance=config.s3instance
            )

        self.image_service_url = config.image_service_url
        self.require_image_service = config.require_image_service

        settings = types.SimpleNamespace(**instance)
        self.log.debug(f"Camera:{self.salinfo.index} settings: {settings}")
        self.config = settings
        self.ip = self.config.ip
        self.port = self.config.port

        self.camera = self.drivers[self.config.camera](log=self.log)
        camera_config = self.config.config
        config_schema = self.camera.get_config_schema()
        validator = salobj.DefaultingValidator(config_schema)
        validator.validate(camera_config)
        self.camera.initialise(config=self.config)

        await self.evt_cameraInfo.set_write(
            cameraMakeAndModel=self.camera.get_make_and_model(),
            **self.camera.get_camera_info(),
            force_output=True,
        )
        top, left, width, height = self.camera.get_roi()
        await self.evt_roi.set_write(
            topPixel=top, leftPixel=left, width=width, height=height, force_output=True
        )

        self.evt_configurationApplied.set(otherInfo="cameraInfo,roi")

    def _assert_notlive(self):
        """Raise an exception if live view is active."""
        assert not self.is_live, "Live view is active."

    def _assert_live(self):
        """Raise an exception if live view is not active."""
        assert self.is_live, "Live view is not active."

    def _assert_notautoexposure(self):
        """Raise an exception if auto exposure is active."""
        assert not self.is_auto_exposure, "Auto exposure is active."

    def _assert_autoexposure(self):
        """Raise an exception if auto exposure is not active."""
        assert self.is_auto_exposure, "Auto exposure is not active."

    def _get_day_obs_and_seq_num_array(
        self, timestamp: float, num_images: int
    ) -> list[int]:
        """Get the DAYOBS and a SEQNUM array

        Parameters
        ----------
        timestamp: `float`
            The timestamp to get the DAYOBS from. Assumed to be on UTC scale.
        num_images: `int`
            The number of images in the sequence.

        Returns
        -------
        seqnum_array: `list[int]`
            The array containing the requested number of image sequence
            numbers.
        """
        day_obs = get_day_obs(timestamp)
        if day_obs != self.day_obs:
            self.day_obs = day_obs
            self.image_sequence_num = 1
        seqnum_array = list(
            range(self.image_sequence_num, self.image_sequence_num + num_images)
        )
        return seqnum_array
