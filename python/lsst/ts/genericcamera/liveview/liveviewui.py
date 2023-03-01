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

__all__ = ["EUI", "run_liveviewui"]

import argparse
import asyncio
import os
import sys
import traceback

import numpy as np
from lsst.ts.genericcamera import version
from lsst.ts.salobj import Domain, Remote
from PIL import Image
from PySide2 import QtCore
from PySide2.QtCore import QTimer
from PySide2.QtGui import QPixmap
from PySide2.QtWidgets import (
    QApplication,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from . import liveview

os.environ["PYQTGRAPH_QT_LIB"] = "PySide2"


def run_liveviewui():
    main(sys.argv)


class EUI(QDialog):
    def __init__(self, ip, port, sal, parent=None):
        super(EUI, self).__init__(parent)
        self.ip = ip
        self.port = port
        self.client = liveview.AsyncLiveViewClient(self.ip, self.port)
        self.event_loop = asyncio.get_event_loop()
        self.event_loop.run_until_complete(self.client.start())
        # self.sal = salobj.Remote(SALPY_GenericCamera, index=salIndex)
        self.sal = sal
        # self.sal.subscribeEvent

        self.layout = QHBoxLayout()
        self.controls_layout = QVBoxLayout()
        self.image_layout = QVBoxLayout()

        layout = QHBoxLayout()
        self.start_live_view_button = QPushButton("Start Live")
        self.start_live_view_button.clicked.connect(self.start_live_view)
        self.stop_live_view_button = QPushButton("Stop Live")
        self.stop_live_view_button.clicked.connect(self.stop_live_view)
        layout.addWidget(self.start_live_view_button)
        layout.addWidget(self.stop_live_view_button)
        self.controls_layout.addLayout(layout)

        layout = QHBoxLayout()
        layout.addWidget(QLabel("Exposure"))
        self.exposure_time_edit = QDoubleSpinBox()
        self.exposure_time_edit.setRange(0, 900.0)
        self.exposure_time_edit.setDecimals(6)
        layout.addWidget(self.exposure_time_edit)
        self.controls_layout.addLayout(layout)

        layout = QVBoxLayout()
        sub_layout = QHBoxLayout()
        sub_layout.addWidget(QLabel("Top"))
        self.roi_top_edit = QDoubleSpinBox()
        self.roi_top_edit.setRange(0, 4095)
        self.roi_top_edit.setDecimals(0)
        sub_layout.addWidget(self.roi_top_edit)
        layout.addLayout(sub_layout)
        sub_layout = QHBoxLayout()
        sub_layout.addWidget(QLabel("Left"))
        self.roi_left_edit = QDoubleSpinBox()
        self.roi_left_edit.setRange(0, 4095)
        self.roi_left_edit.setDecimals(0)
        sub_layout.addWidget(self.roi_left_edit)
        layout.addLayout(sub_layout)
        sub_layout = QHBoxLayout()
        sub_layout.addWidget(QLabel("Width"))
        self.roi_width_edit = QDoubleSpinBox()
        self.roi_width_edit.setRange(0, 4095)
        self.roi_width_edit.setDecimals(0)
        sub_layout.addWidget(self.roi_width_edit)
        layout.addLayout(sub_layout)
        sub_layout = QHBoxLayout()
        sub_layout.addWidget(QLabel("Height"))
        self.roi_height_edit = QDoubleSpinBox()
        self.roi_height_edit.setRange(0, 4095)
        self.roi_height_edit.setDecimals(0)
        sub_layout.addWidget(self.roi_height_edit)
        layout.addLayout(sub_layout)
        self.set_roi_button = QPushButton("Set")
        self.set_roi_button.clicked.connect(self.set_roi)
        layout.addWidget(self.set_roi_button)
        self.set_full_frame_button = QPushButton("Set Full Frame")
        self.set_full_frame_button.clicked.connect(self.set_full_frame)
        layout.addWidget(self.set_full_frame_button)
        self.controls_layout.addLayout(layout)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("File Path:"))
        self.file_path_edit = QTextEdit()
        layout.addWidget(self.file_path_edit)
        self.take_exposure_button = QPushButton("Take Images")
        self.take_exposure_button.clicked.connect(self.take_images)
        layout.addWidget(self.take_exposure_button)
        self.controls_layout.addLayout(layout)

        img = Image.fromarray(np.zeros((1024, 1014))).convert("I")
        img.save("/tmp/foo.png")

        self.pix = QPixmap("/tmp/foo.png")

        self.image_label = QLabel()
        self.image_label.setPixmap(self.pix)
        self.image_label.setGeometry(QtCore.QRect(40, 40, 800, 800))

        self.image_layout.addWidget(self.image_label)

        self.layout.addLayout(self.controls_layout)
        self.layout.addLayout(self.image_layout)

        self.setLayout(self.layout)
        self.setFixedSize(1000, 880)

    def update_displays(self):
        print("updateDisplays - Here - 1")
        try:
            if self.client is None or self.client.reader is not None:
                try:
                    print("updateDisplays - Here - 2")
                    self.client = liveview.AsyncLiveViewClient(self.ip, self.port)
                    self.event_loop.run_until_complete(self.client.start())
                except Exception:
                    print("Error on client!")
                    self.client = None
            print("updateDisplays - Here - 3")
            exposure = self.event_loop.run_until_complete(
                self.client.receive_exposure()
            )
            print("New exposure.")
            # exposure.make_jpeg()
            # img = Image.open(BytesIO(exposure.buffer))
            # width = img.size[0]
            # height = img.size[1]
            # ratio = width / height
            # deltaWidth = width - 760
            # deltaHeight = height - 760
            # if deltaWidth > 0 or deltaHeight > 0:
            #     newWidth = 760
            #     newHeight = 760
            #     if deltaWidth > deltaHeight:
            #         newWidth = newWidth
            #         newHeight = newHeight / ratio
            #     elif deltaHeight > deltaWidth:
            #         newWidth = newWidth / ratio
            #         newHeight = newHeight
            #     img = img.resize((int(newWidth), int(newHeight)))
            as8 = exposure.buffer.astype(np.uint8)
            img = Image.fromarray(as8.reshape(exposure.height, exposure.width))
            img.save("/tmp/foo.png")

            self.pix = QPixmap("/tmp/foo.png")

            self.image_label.setPixmap(self.pix)
        except liveview.ImageReceiveError as e:
            print("updateDisplays - Exception")
            traceback.format_exc(e)
            pass

    def start_live_view(self):
        print("start_live_view - Start")
        # data = self.sal.cmd_startLiveView.DataType()
        # data.expTime = self.exposure_time_edit.value()
        # asyncio.get_event_loop().run_until_complete(
        #     self.sal.cmd_startLiveView.start(data, timeout=10.0)
        # )
        self.sal.issueCommand_startLiveView(self.exposure_time_edit.value())
        print("start_live_view - End")

    def stop_live_view(self):
        print("stop_live_view - Start")
        # asyncio.get_event_loop().run_until_complete(
        #     self.sal.cmd_stopLiveView.start(
        # self.sal.cmd_stopLiveView.DataType(), timeout=10.0))
        self.sal.issueCommand_stopLiveView(True)
        print("stop_live_view - End")

    def set_roi(self):
        print("set_roi - Start")
        # data = self.sal.cmd_setROI.DataType()
        # data.topPixel = int(self.roiTopEdit.value())
        # data.leftPixel = int(self.roiLeftEdit.value())
        # data.width = int(self.roiWidthEdit.value())
        # data.height = int(self.roiHeightEdit.value())
        # asyncio.get_event_loop().run_until_complete(
        #     self.sal.cmd_setROI.start(data, timeout=5.0)
        # )
        self.sal.issueCommand_setROI(
            int(self.roi_top_edit.value()),
            int(self.roi_left_edit.value()),
            int(self.roi_width_edit.value()),
            int(self.roi_height_edit.value()),
        )
        print("set_roi - End")

    def set_full_frame(self):
        print("set_full_frame - Start")
        # asyncio.get_event_loop().run_until_complete(self.sal.cmd_setFullFrame.start(
        # self.sal.cmd_setFullFrame.DataType(), timeout=5.0))
        self.sal.issueCommand_setFullFrame(True)
        print("set_full_frame - End")

    def take_images(self):
        print("take_images - Start")
        # data = self.sal.cmd_takeImages.DataType()
        # data.numImages = 1
        # data.expTime = self.exposure_time_edit.value()
        # data.shutter = 1
        # data.imageSequenceName = "Foo"
        # asyncio.get_event_loop().run_until_complete(self.sal.cmd_takeImages.start(data,
        # timeout=30.0))
        self.sal.issueCommand_takeImages(1, self.exposure_time_edit.value(), 1, "Foo")
        print("take_images - End")


def main(argv):
    parser = argparse.ArgumentParser("Start the GenericCamera CSC")
    parser.add_argument("--version", action="version", version=version.__version__)
    parser.add_argument(
        "-p", "--port", type=int, default=5013, help="TCP/IP port of live view server."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="TCP/IP host address of live view server.",
    )

    args = parser.parse_args(argv[1:])

    # Create the Qt Application
    domain = Domain()
    remote = Remote(domain, name="GenericCamera", index=1)

    app = QApplication(sys.argv)
    # Create EUI
    eui = EUI(args.host, args.port, remote, None)
    eui.show()
    update_timer = QTimer()
    update_timer.timeout.connect(eui.update_displays)
    update_timer.start(100)
    sal_timer = QTimer()
    # sal_timer.timeout.connect(sal.runSubscriberChecks())
    sal_timer.start(10)
    # Create MTM1M3 Telemetry & Event Loop & Display update
    # Run the main Qt loop
    app.exec_()
    # Clean up MTM1M3 Telemetry & Event Loop
    # Close application
    sys.exit()


if __name__ == "__main__":
    main(sys.argv)
