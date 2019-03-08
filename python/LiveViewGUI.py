import os

os.environ["PYQTGRAPH_QT_LIB"] = "PySide2"

import sys
import time

from PySide2.QtCore import QTimer
from PySide2.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QDialog, QLabel, QPushButton, QDoubleSpinBox, QTextEdit)
from PySide2.QtGui import (QFont, QPixmap)
from PySide2 import QtCore
from PIL import Image
from PIL.ImageQt import ImageQt
from io import BytesIO

from GenericCameraInterface import *

from lsst.ts import salobj
import SALPY_GenericCamera

class EUI(QDialog):
    def __init__(self, ip, port, salIndex, parent=None):
        super(EUI, self).__init__(parent)
        self.ip = ip
        self.port = port
        self.client = None
        
        self.sal = salobj.Remote(SALPY_GenericCamera, index=salIndex)
        self.sal.salinfo.manager.setDebugLevel(0)
        
        self.layout = QHBoxLayout()
        self.controlsLayout = QVBoxLayout()
        self.imageLayout = QVBoxLayout()

        layout = QHBoxLayout()
        self.startLiveViewButton = QPushButton("Start Live")
        self.startLiveViewButton.clicked.connect(self.startLiveView)
        self.stopLiveViewButton = QPushButton("Stop Live")
        self.stopLiveViewButton.clicked.connect(self.stopLiveView)
        layout.addWidget(self.startLiveViewButton)
        layout.addWidget(self.stopLiveViewButton)
        self.controlsLayout.addLayout(layout)
        self.resumeLiveViewButton = QPushButton("Resume Live")
        self.resumeLiveViewButton.clicked.connect(self.resumeLiveView)
        self.controlsLayout.addWidget(self.resumeLiveViewButton)

        layout = QHBoxLayout()
        layout.addWidget(QLabel("Exposure"))
        self.exposureTimeEdit = QDoubleSpinBox()
        self.exposureTimeEdit.setRange(0, 900.0)
        self.exposureTimeEdit.setDecimals(6)
        layout.addWidget(self.exposureTimeEdit)
        self.setExposureTimeButton = QPushButton("Set")
        self.setExposureTimeButton.clicked.connect(self.setExposureTime)
        layout.addWidget(self.setExposureTimeButton)
        self.controlsLayout.addLayout(layout)

        layout = QVBoxLayout()
        subLayout = QHBoxLayout()
        subLayout.addWidget(QLabel("Top"))
        self.roiTopEdit = QDoubleSpinBox()
        self.roiTopEdit.setRange(0, 4095)
        self.roiTopEdit.setDecimals(0)
        subLayout.addWidget(self.roiTopEdit)
        layout.addLayout(subLayout)
        subLayout = QHBoxLayout()
        subLayout.addWidget(QLabel("Left"))
        self.roiLeftEdit = QDoubleSpinBox()
        self.roiLeftEdit.setRange(0, 4095)
        self.roiLeftEdit.setDecimals(0)
        subLayout.addWidget(self.roiLeftEdit)
        layout.addLayout(subLayout)
        subLayout = QHBoxLayout()
        subLayout.addWidget(QLabel("Width"))
        self.roiWidthEdit = QDoubleSpinBox()
        self.roiWidthEdit.setRange(0, 4095)
        self.roiWidthEdit.setDecimals(0)
        subLayout.addWidget(self.roiWidthEdit)
        layout.addLayout(subLayout)
        subLayout = QHBoxLayout()
        subLayout.addWidget(QLabel("Height"))
        self.roiHeightEdit = QDoubleSpinBox()
        self.roiHeightEdit.setRange(0, 4095)
        self.roiHeightEdit.setDecimals(0)
        subLayout.addWidget(self.roiHeightEdit)
        layout.addLayout(subLayout)
        self.setROIButton = QPushButton("Set")
        self.setROIButton.clicked.connect(self.setROI)
        layout.addWidget(self.setROIButton)
        self.setFullFrameButton = QPushButton("Set Full Frame")
        self.setFullFrameButton.clicked.connect(self.setFullFrame)
        layout.addWidget(self.setFullFrameButton)
        self.controlsLayout.addLayout(layout)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("File Path:"))
        self.filePathEdit = QTextEdit()
        layout.addWidget(self.filePathEdit)
        self.takeExposureButton = QPushButton("Take Exposure")
        self.takeExposureButton.clicked.connect(self.takeExposure)
        layout.addWidget(self.takeExposureButton)
        self.controlsLayout.addLayout(layout)
        
        img = Image.open("/home/ccontaxis/Foo11.jpg")
        img = img.resize((760, 760))
        self.pix = QPixmap.fromImage(ImageQt(img))
        
        self.imageLabel = QLabel()
        self.imageLabel.setPixmap(self.pix)
        self.imageLabel.setGeometry(QtCore.QRect(40, 40, 800, 800))
        
        self.imageLayout.addWidget(self.imageLabel)

        self.layout.addLayout(self.controlsLayout)
        self.layout.addLayout(self.imageLayout)

        self.setLayout(self.layout)
        self.setFixedSize(1000, 880)

    def updateDisplays(self):
        if self.client is not None:
            try:
                exposure = self.client.receiveExposure()
                img = Image.open(BytesIO(exposure.buffer))
                width = img.size[0]
                height = img.size[1]
                ratio = width / height
                deltaWidth = width - 760
                deltaHeight = height - 760
                if deltaWidth > 0 or deltaHeight > 0:
                    newWidth = 760
                    newHeight = 760
                    if deltaWidth > deltaHeight:
                        newWidth = newWidth
                        newHeight = newHeight / ratio
                    elif deltaHeight > deltaWidth:
                        newWidth = newWidth / ratio
                        newHeight = newHeight
                    img = img.resize((int(newWidth), int(newHeight)))
                self.pix = QPixmap.fromImage(ImageQt(img))
                self.imageLabel.setPixmap(self.pix)
            except ImageReceiveError:
                pass

    def startLiveView(self):
        if self.client is None:
            self.sal.cmd_startLiveView.start(self.sal.cmd_startLiveView.DataType(), timeout=1.0)
            time.sleep(0.5)
            self.client = LiveViewClient(self.ip, self.port)
        pass

    def stopLiveView(self):
        if self.client is not None:
            self.sal.cmd_stopLiveView.start(self.sal.cmd_stopLiveView.DataType(), timeout=1.0)
            self.client.close()
            self.client = None

    def resumeLiveView(self):
        if self.client is None:
            self.client = LiveViewClient(self.ip, self.port)

    def setExposureTime(self):
        if self.client is None:
            data = self.sal.cmd_setExposureTime.DataType()
            data.exposureTimeInSec = self.exposureTimeEdit.value()
            self.sal.cmd_setExposureTime.start(data, timeout=1.0)

    def setROI(self):
        if self.client is None:
            data = self.sal.cmd_setROI.DataType()
            data.topPixel = int(self.roiTopEdit.value())
            data.leftPixel = int(self.roiLeftEdit.value())
            data.width = int(self.roiWidthEdit.value())
            data.height = int(self.roiHeightEdit.value())
            self.sal.cmd_setROI.start(data, timeout=1.0)

    def setFullFrame(self):
        if self.client is None:
            self.sal.cmd_setFullFrame.start(self.sal.cmd_setFullFrame.DataType(), timeout=1.0)

    def takeExposure(self):
        if self.client is None:
            data = self.sal.cmd_takeExposure.DataType()
            data.filePath = self.filePathEdit.toPlainText()
            self.sal.cmd_takeExposure.start(data, timeout=1.0)


if __name__ == '__main__':
    # Create the Qt Application
    app = QApplication(sys.argv)
    # Create EUI
    eui = EUI('127.0.0.1', 5005, 0)
    eui.show()
    updateTimer = QTimer()
    updateTimer.timeout.connect(eui.updateDisplays)
    updateTimer.start(1)
    # Create MTM1M3 Telemetry & Event Loop & Display update
    # Run the main Qt loop
    app.exec_()
    # Clean up MTM1M3 Telemetry & Event Loop
    # Close application
    sys.exit()
