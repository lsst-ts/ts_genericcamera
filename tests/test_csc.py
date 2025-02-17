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

import asyncio
import contextlib
import glob
import os
import pathlib
import shutil
import unittest

import numpy as np
import yaml
from lsst.ts import genericcamera, salobj, utils
from requests import ConnectionError

STD_TIMEOUT = 2  # standard command timeout (sec)
TEST_CONFIG_DIR = pathlib.Path(__file__).parent / "data" / "config"
TEST_HEADER_DIR = pathlib.Path(__file__).parent / "data" / "header"


class CscTestCase(salobj.BaseCscTestCase, unittest.IsolatedAsyncioTestCase):
    @contextlib.asynccontextmanager
    async def make_csc(
        self,
        initial_state,
        config_dir=None,
        override="",
        simulation_mode=0,
        log_level=None,
    ):
        async with super().make_csc(
            initial_state=initial_state,
            config_dir=config_dir,
            override=override,
            simulation_mode=simulation_mode,
            log_level=log_level,
        ), genericcamera.MockGCHeaderService(
            index=1, initial_state=salobj.State.ENABLED
        ) as self.gchs_csc:
            yield

    @classmethod
    def setUpClass(cls):
        cls.data_dir = pathlib.Path.home() / "data"
        cls.data_dir.mkdir(exist_ok=True)
        header_file = TEST_HEADER_DIR / "header.yaml"
        cls.header_contents = header_file.read_bytes()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.data_dir)

    def flush_take_image_events(self):
        self.remote.evt_startTakeImage.flush()
        self.remote.evt_startShutterOpen.flush()
        self.remote.evt_endShutterOpen.flush()
        self.remote.evt_startIntegration.flush()
        self.remote.evt_endIntegration.flush()
        self.remote.evt_startShutterClose.flush()
        self.remote.evt_endShutterClose.flush()
        self.remote.evt_startReadout.flush()
        self.remote.evt_endReadout.flush()
        self.remote.evt_largeFileObjectAvailable.flush()
        self.remote.evt_endTakeImage.flush()

    def basic_make_csc(self, initial_state, config_dir, simulation_mode, **kwargs):
        return genericcamera.GenericCameraCsc(
            initial_state=initial_state,
            config_dir=config_dir,
            simulation_mode=0,
            index=1,
        )

    async def test_default_config_dir(self):
        async with self.make_csc(initial_state=salobj.State.STANDBY):
            self.assertEqual(self.csc.summary_state, salobj.State.STANDBY)

            desired_config_pkg_name = "ts_config_ocs"
            desired_config_env_name = desired_config_pkg_name.upper() + "_DIR"
            desired_config_pkg_dir = os.environ[desired_config_env_name]
            desired_config_dir = pathlib.Path(
                desired_config_pkg_dir
            ) / genericcamera.CONFIG_SCHEMA["title"].replace(" ", "/")
            self.assertEqual(self.csc.get_config_pkg(), desired_config_pkg_name)
            self.assertEqual(self.csc.config_dir, desired_config_dir)

    async def test_configuration(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR
        ):
            self.assertEqual(self.csc.summary_state, salobj.State.STANDBY)
            await self.assert_next_summary_state(
                state=salobj.State.STANDBY,
                remote=self.remote,
            )

            overrides = [
                "all_fields.yaml",
                "invalid_bad_camera_driver.yaml",
                "invalid_malformed.yaml",
                "mock_lfa.yaml",
                "use_image_service.yaml",
            ]

            await self.assert_next_sample(
                self.remote.evt_configurationsAvailable, overrides=",".join(overrides)
            )

            invalid_files = glob.glob(os.path.join(TEST_CONFIG_DIR, "invalid_*.yaml"))
            bad_config_names = [os.path.basename(name) for name in invalid_files]
            bad_config_names.append("no_such_file.yaml")
            for bad_config_name in bad_config_names:
                with self.subTest(bad_config_name=bad_config_name):
                    self.remote.cmd_start.set(configurationOverride=bad_config_name)
                    with self.assertRaises(salobj.AckError):
                        await self.remote.cmd_start.start(timeout=STD_TIMEOUT)

            self.remote.cmd_start.set(configurationOverride="all_fields.yaml")
            await self.remote.cmd_start.start(timeout=STD_TIMEOUT)
            self.assertEqual(self.csc.summary_state, salobj.State.DISABLED)
            await self.assert_next_summary_state(
                state=salobj.State.DISABLED,
                remote=self.remote,
            )

            await self.assert_next_sample(
                self.remote.evt_configurationApplied,
                configurations="_init.yaml,all_fields.yaml",
                otherInfo="cameraInfo,roi",
            )

            await self.assert_next_sample(
                self.remote.evt_cameraInfo,
                cameraMakeAndModel="Simulator",
                lensFocalLength=100.0,
                lensDiameter=50.0,
            )

            await self.assert_next_sample(
                self.remote.evt_roi,
                topPixel=0,
                leftPixel=0,
                width=1024,
                height=1024,
            )

            all_fields_path = os.path.join(TEST_CONFIG_DIR, "all_fields.yaml")
            with open(all_fields_path, "r") as f:
                all_fields_raw = f.read()
            all_fields_data = yaml.safe_load(all_fields_raw)
            instance = all_fields_data["instances"][0]
            for field, value in instance.items():
                self.assertEqual(getattr(self.csc.config, field), value)

    async def test_state_transition(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR
        ):

            async def check_rejected(expected_state):
                self.assertEqual(self.csc.summary_state, expected_state)
                await self.assert_next_summary_state(
                    state=expected_state,
                    remote=self.remote,
                )

                extra_commands = (
                    "setROI",
                    "setFullFrame",
                    "startLiveView",
                    "stopLiveView",
                    "takeImages",
                    "startStreamingMode",
                    "stopStreamingMode",
                )

                for bad_command in extra_commands:
                    with self.subTest(bad_command=bad_command):
                        cmd_attr = getattr(self.remote, f"cmd_{bad_command}")
                        with self.assertRaises(salobj.AckError):
                            await cmd_attr.start(cmd_attr.DataType(), timeout=1.0)

            await check_rejected(salobj.State.STANDBY)

            await salobj.set_summary_state(self.remote, salobj.State.DISABLED)

            await check_rejected(salobj.State.DISABLED)

            await salobj.set_summary_state(self.remote, salobj.State.ENABLED)

            self.assertEqual(self.csc.summary_state, salobj.State.ENABLED)
            await self.assert_next_summary_state(
                state=salobj.State.ENABLED,
                remote=self.remote,
            )

            await salobj.set_summary_state(self.remote, salobj.State.DISABLED)

            await check_rejected(salobj.State.DISABLED)

            await salobj.set_summary_state(self.remote, salobj.State.STANDBY)

            await check_rejected(salobj.State.STANDBY)

    async def test_take_image(self):
        self.mock_response = unittest.mock.Mock()
        self.mock_response.status_code = 200
        self.mock_response.json.side_effect = [
            ["GC1_O_20220822_000001"],
            ["GC1_O_20220822_000002"],
            ["GC1_O_20220822_000005"],
            ["GC1_O_20220822_000006"],
        ]
        self.mock_response.content = self.header_contents

        @unittest.mock.patch("lsst.ts.genericcamera.requests.get")
        async def take_bias(mock_get):
            mock_get.side_effect = [ConnectionError(), self.mock_response]

            await self.remote.cmd_takeImages.set_start(
                numImages=1,
                expTime=0.0,
                shutter=False,
                sensors="",
                keyValueMap="imageType: BIAS, groupId: CALIBSET_20220823, testType: BIAS",
                obsNote="bias",
            )

            startTakeImage = await self.assert_next_sample(
                self.remote.evt_startTakeImage
            )
            self.assertIsNotNone(startTakeImage)

            with self.assertRaises(asyncio.TimeoutError):
                await self.assert_next_sample(self.remote.evt_startShutterOpen)

            with self.assertRaises(asyncio.TimeoutError):
                await self.assert_next_sample(self.remote.evt_endShutterOpen)

            await self.assert_next_sample(
                self.remote.evt_startIntegration,
                additionalKeys="imageType:groupId:testType",
                additionalValues="BIAS:CALIBSET_20220823:BIAS",
            )

            await self.assert_next_sample(
                self.remote.evt_endIntegration,
                additionalKeys="imageType:groupId:testType",
                additionalValues="BIAS:CALIBSET_20220823:BIAS",
            )

            with self.assertRaises(asyncio.TimeoutError):
                await self.assert_next_sample(
                    self.remote.evt_startShutterClose,
                )

            with self.assertRaises(asyncio.TimeoutError):
                await self.assert_next_sample(self.remote.evt_endShutterClose)

            await self.assert_next_sample(
                self.remote.evt_startReadout,
                additionalKeys="imageType:groupId:testType",
                additionalValues="BIAS:CALIBSET_20220823:BIAS",
            )

            await self.assert_next_sample(
                self.remote.evt_endReadout,
                additionalKeys="imageType:groupId:testType",
                additionalValues="BIAS:CALIBSET_20220823:BIAS",
            )

            endTakeImage = await self.assert_next_sample(self.remote.evt_endTakeImage)
            self.assertIsNotNone(endTakeImage)

        @unittest.mock.patch("lsst.ts.genericcamera.requests.get")
        async def take_image(image_name_check, check_lfoa, mock_get):
            mock_get.return_value = self.mock_response
            await self.remote.cmd_takeImages.set_start(
                numImages=1,
                expTime=np.random.rand() + 1.0,
                shutter=True,
                sensors="",
                keyValueMap="imageType: ENGTEST, groupId: TestGroup",
                obsNote="image",
            )

            startTakeImage = await self.assert_next_sample(
                self.remote.evt_startTakeImage
            )
            self.assertIsNotNone(startTakeImage)

            startShutterOpen = await self.assert_next_sample(
                self.remote.evt_startShutterOpen
            )
            self.assertIsNotNone(startShutterOpen)

            endShutterOpen = await self.assert_next_sample(
                self.remote.evt_endShutterOpen
            )
            self.assertIsNotNone(endShutterOpen)

            await self.assert_next_sample(
                self.remote.evt_startIntegration,
                imageSource=self.csc.image_source,
                imageController=self.csc.image_controller,
                imageNumber=self.csc.image_sequence_num - 1,
                imageDate=self.csc.day_obs,
                additionalKeys="imageType:groupId",
                additionalValues="ENGTEST:TestGroup",
                imageName=image_name_check,
            )

            await self.assert_next_sample(
                self.remote.evt_endIntegration,
                additionalKeys="imageType:groupId",
                additionalValues="ENGTEST:TestGroup",
            )

            startShutterClose = await self.assert_next_sample(
                self.remote.evt_startShutterClose
            )
            self.assertIsNotNone(startShutterClose)

            endShutterClose = await self.assert_next_sample(
                self.remote.evt_endShutterClose
            )
            self.assertIsNotNone(endShutterClose)

            await self.assert_next_sample(
                self.remote.evt_startReadout,
                imageSource=self.csc.image_source,
                imageController=self.csc.image_controller,
                imageNumber=self.csc.image_sequence_num - 1,
                imageDate=self.csc.day_obs,
                additionalKeys="imageType:groupId",
                additionalValues="ENGTEST:TestGroup",
                imageName=image_name_check,
            )

            await self.assert_next_sample(
                self.remote.evt_endReadout,
                imageSource=self.csc.image_source,
                imageController=self.csc.image_controller,
                imageNumber=self.csc.image_sequence_num - 1,
                imageDate=self.csc.day_obs,
                additionalKeys="imageType:groupId",
                additionalValues="ENGTEST:TestGroup",
                imageName=image_name_check,
            )

            if check_lfoa:
                largeFileObjectAvailable = await self.assert_next_sample(
                    self.remote.evt_largeFileObjectAvailable
                )
                self.assertIsNotNone(largeFileObjectAvailable)

            endTakeImage = await self.assert_next_sample(self.remote.evt_endTakeImage)
            self.assertIsNotNone(endTakeImage)

        @unittest.mock.patch("lsst.ts.genericcamera.requests.get")
        async def take_image_no_image_service(image_name_check, mock_get):
            mock_get.side_effect = [
                ConnectionError("Cannot connect to image service"),
                self.mock_response,
            ]
            await self.remote.cmd_takeImages.set_start(
                numImages=1,
                expTime=np.random.rand() + 1.0,
                shutter=True,
                sensors="",
                keyValueMap="imageType: ENGTEST, groupId: TestGroup",
                obsNote="image",
            )

        @unittest.mock.patch("lsst.ts.genericcamera.requests.get")
        async def take_image_image_service_bad_status_code(image_name_check, mock_get):
            self.mock_response.status_code = 400
            mock_get.return_value = self.mock_response
            await self.remote.cmd_takeImages.set_start(
                numImages=1,
                expTime=np.random.rand() + 1.0,
                shutter=True,
                sensors="",
                keyValueMap="imageType: ENGTEST, groupId: TestGroup",
                obsNote="image",
            )

        async with self.make_csc(
            initial_state=salobj.State.ENABLED, config_dir=TEST_CONFIG_DIR
        ):
            self.gchs_csc.set_take_image_list()
            await self.assert_next_summary_state(
                state=salobj.State.ENABLED,
                remote=self.remote,
            )

            self.flush_take_image_events()

            # Take 2 images with random exposure time
            with self.subTest(image="image1"):
                await take_image("GC1_O_20220822_000001", False)

            with self.subTest(image="image2"):
                await take_image("GC1_O_20220822_000002", False)

            # Try taking 2 bias
            with self.subTest(image="bias1"):
                await take_bias()

            with self.subTest(image="bias2"):
                await take_bias()

            await salobj.set_summary_state(self.remote, salobj.State.STANDBY)
            await salobj.set_summary_state(
                self.remote, salobj.State.ENABLED, override="use_image_service.yaml"
            )

            with self.subTest(image="image3"):
                await take_image("GC1_O_20220822_000005", False)

            with self.subTest(image="image4"):
                with self.assertRaises(salobj.AckError):
                    await take_image_no_image_service("")

            with self.subTest(image="image5"):
                with self.assertRaises(salobj.AckError):
                    await take_image_image_service_bad_status_code("")

            # Run with LFA
            await salobj.set_summary_state(self.remote, salobj.State.STANDBY)
            with utils.modify_environ(
                AWS_ACCESS_KEY_ID="test",
                AWS_SECRET_ACCESS_KEY="bar",
            ):
                await salobj.set_summary_state(
                    self.remote, salobj.State.ENABLED, override="mock_lfa.yaml"
                )
                self.flush_take_image_events()

                self.mock_response.status_code = 200
                with self.subTest(image="image6"):
                    await take_image("GC1_O_20220822_000006", True)

    async def test_live_view(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR
        ):
            await salobj.set_summary_state(self.remote, salobj.State.ENABLED)

            self.flush_take_image_events()

            # Check that LiveView fails if exptime = 0
            with self.assertRaises(salobj.AckError):
                await self.remote.cmd_startLiveView.start()

            client = genericcamera.AsyncLiveViewClient("127.0.0.1", 5013)

            # Start Liveview and get a series of images
            self.remote.evt_startLiveView.flush()
            await self.remote.cmd_startLiveView.set_start(expTime=1.0)

            lv_start = await self.assert_next_sample(self.remote.evt_startLiveView)

            self.assertIsNotNone(lv_start)

            await client.start()

            r_exp = await client.receive_exposure()

            self.assertIsNotNone(r_exp)

            await self.remote.cmd_stopLiveView.start()

    @unittest.mock.patch("lsst.ts.genericcamera.requests.get")
    async def test_auto_exposure(self, mock_get):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            ["GC1_O_20220830_000001"],
            ["GC1_O_20220830_000002"],
            ["GC1_O_20220830_000003"],
            ["GC1_O_20220830_000004"],
        ]
        mock_response.content = self.header_contents
        mock_get.return_value = mock_response

        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR
        ):
            self.gchs_csc.set_auto_exposure_list()
            await salobj.set_summary_state(self.remote, salobj.State.ENABLED)

            # Set the auto exposure time interval to a low value so
            # the test doesn't take so long
            self.csc.config.auto_exposure_interval = 2.0

            self.flush_take_image_events()

            await self.remote.cmd_startAutoExposure.set_start(
                minExpTime=1.0, maxExpTime=10.0, configuration=""
            )
            ae_start = await self.assert_next_sample(
                self.remote.evt_autoExposureStarted
            )
            self.assertIsNotNone(ae_start)

            ti_start = await self.assert_next_sample(self.remote.evt_startTakeImage)
            self.assertIsNotNone(ti_start)
            ti_end = await self.assert_next_sample(self.remote.evt_endTakeImage)
            self.assertIsNotNone(ti_end)

            ti_start = await self.assert_next_sample(self.remote.evt_startTakeImage)
            self.assertIsNotNone(ti_start)
            ti_end = await self.assert_next_sample(self.remote.evt_endTakeImage)
            self.assertIsNotNone(ti_end)

            await self.remote.cmd_stopAutoExposure.start()
            ae_stop = await self.assert_next_sample(self.remote.evt_autoExposureStopped)
            self.assertIsNotNone(ae_stop)

    async def test_version(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR
        ):
            await self.assert_next_sample(
                self.remote.evt_softwareVersions,
                cscVersion=genericcamera.__version__,
                subsystemVersions="",
            )

    async def test_set_full_frame(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR
        ):
            await salobj.set_summary_state(self.remote, salobj.State.ENABLED)
            self.remote.evt_roi.flush()
            await self.remote.cmd_setFullFrame.start(timeout=STD_TIMEOUT)

            await self.assert_next_sample(
                self.remote.evt_roi,
                topPixel=0,
                leftPixel=0,
                width=1024,
                height=1024,
            )

    @unittest.mock.patch("lsst.ts.genericcamera.requests.get")
    async def test_streaming_mode(self, mock_get):
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            ["GC1_O_20230926_000001"],
        ]

        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR
        ):
            await salobj.set_summary_state(self.remote, salobj.State.ENABLED)

            exposure_time = 0.01
            await self.remote.cmd_startStreamingMode.set_start(expTime=exposure_time)

            await self.assert_next_sample(
                self.remote.evt_streamingModeStarted,
                expTime=exposure_time,
            )

            await self.remote.cmd_stopStreamingMode.start()

            sm_stop = await self.assert_next_sample(
                self.remote.evt_streamingModeStopped,
                expTime=exposure_time,
            )
            self.assertNotEqual(sm_stop.numFrames, 0)
            self.assertNotEqual(sm_stop.avgFrameRate, 0)
