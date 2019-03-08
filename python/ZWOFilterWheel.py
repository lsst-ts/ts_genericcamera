
import enum
import ctypes
from ctypes import c_int, POINTER
from ctypes.util import find_library


class Results(enum.Enum):
    Success = 0
    InvalidIndex = 1
    InvalidId = 2
    InvalidValue = 3
    Removed = 4
    Moving = 5
    ErrorState = 6
    GeneralError = 7
    NotSupported = 8
    Closed = 9
    End = -1


class EFW():
    def __init__(self):
        # The udev library must be loaded first before the EFWFilter library
        # can be loaded otherwise an OSError is generated
        udev = ctypes.CDLL(find_library("udev"), mode=ctypes.RTLD_GLOBAL)
        lib = ctypes.CDLL(find_library("EFWFilter"), mode=ctypes.RTLD_GLOBAL)

        # EFW_API int EFWGetNum();
        lib.EFWGetNum.restype = c_int

        # EFW_API int EFWGetProductIDs(int* pPIDs);
        lib.EFWGetProductIDs.argtypes = [c_int * 16]
        lib.EFWGetProductIDs.restype = c_int

        # EFW_API EFW_ERROR_CODE EFWGetID(int index, int* ID);
        lib.EFWGetID.argtypes = [c_int, POINTER(c_int)]
        lib.EFWGetID.restype = c_int

        # EFW_API	EFW_ERROR_CODE EFWOpen(int ID);
        lib.EFWOpen.argtypes = [c_int]
        lib.EFWOpen.restype = c_int

        # EFW_API	EFW_ERROR_CODE EFWGetPosition(int ID, int *pPosition);
        lib.EFWGetPosition.argtypes = [c_int, POINTER(c_int)]
        lib.EFWGetPosition.restype = c_int

        # EFW_API	EFW_ERROR_CODE EFWSetPosition(int ID, int Position);
        lib.EFWSetPosition.argtypes = [c_int, c_int]
        lib.EFWSetPosition.restype = c_int

        # EFW_API	EFW_ERROR_CODE EFWClose(int ID);
        lib.EFWClose.argtypes = [c_int]
        lib.EFWClose.restype = c_int

        self.udev = udev
        self.lib = lib
        self.intPtr = POINTER(c_int)

    def getNumberOfDevices(self):
        # EFW_API int EFWGetNum();
        return self.lib.EFWGetNum()

    def getProductIDs(self):
        # EFW_API int EFWGetProductIDs(int* pPIDs);
        dataType = c_int * 16
        productIDs = dataType(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        count = self.lib.EFWGetProductIDs(productIDs)
        return [productIDs[i] for i in range(count)]

    def getProductID(self, index):
        # EFW_API EFW_ERROR_CODE EFWGetID(int index, int* ID);
        productID = self._getIntPtr()
        result = self.lib.EFWGetID(index, productID)
        return self._toResultEnum(result), productID[0]

    def open(self, id):
        # EFW_API	EFW_ERROR_CODE EFWOpen(int ID);
        result = self.lib.EFWOpen(id)
        return self._toResultEnum(result)

    def getPosition(self, id):
        # EFW_API	EFW_ERROR_CODE EFWGetPosition(int ID, int *pPosition);
        position = self._getIntPtr()
        result = self.lib.EFWGetPosition(id, position)
        return self._toResultEnum(result), position[0]

    def setPosition(self, id, position):
        # EFW_API	EFW_ERROR_CODE EFWSetPosition(int ID, int Position);
        result = self.lib.EFWSetPosition(id, position)
        return self._toResultEnum(result)

    def close(self, id):
        # EFW_API	EFW_ERROR_CODE EFWClose(int ID);
        result = self.lib.EFWClose(id)
        return self._toResultEnum(result)

    def _getIntPtr(self, defaultValue=0):
        return self.intPtr(c_int(defaultValue))

    def _toResultEnum(self, result):
        return Results(result)


class EFWError(Exception):
    def __init__(self, result : Results):
        super().__init__()
        self.result = result

    def __str__(self):
        return self.result.name


class EFWLibraryNotInitialised(Exception):
    def __init__(self):
        super().__init__()


class EFWDeviceNotOpenError(Exception):
    def __init__(self):
        super().__init__()


class EFWBase(object):
    def __init__(self, efw=None):
        if efw is None:
            self.efw = EFW()
        else:
            self.efw = efw

    def _raiseIfBad(self, result : Results):
        if result != Results.Success:
            raise EFWError(result)


class EFWLibrary(EFWBase):
    def __init__(self, efw=None):
        super().__init__(efw)
        self.initialised = False

    def initialiseLibrary(self):
        """Initialise the ZWO SDK Library.
        """
        if not self.initialised:
            self.efw.getNumberOfDevices()
            self.initialised = True

    def getDeviceCount(self):
        """Gets the number of ZWO filter wheels attached to this machine.

        Returns
        -------
        int
            The number of filter wheels attached to this machine."""
        if not self.initialised:
            raise EFWLibraryNotInitialised()
        deviceCount = self.efw.getNumberOfDevices()
        return deviceCount

    def getProductIDs(self):
        """Gets the product IDs of all the ZWO filter wheels attached to this machine.

        Returns
        -------
        int list
            The product IDs of the filter wheels attached to this machine."""
        if not self.initialised:
            raise EFWLibraryNotInitialised()
        productIDs = self.efw.getProductIDs()
        return productIDs

    def openEFW(self, index):
        """Opens the specified ZWO filter wheel attached to this machine.

        Parameters
        ----------
        index : int
            The index (0 to getDeviceCount()) of the filter wheel to open.

        Returns
        -------
        EFWDevice
            The filter wheel device."""
        if not self.initialised:
            raise EFWLibraryNotInitialised()
        device = EFWDevice(index, self.efw)
        return device

class EFWDevice(EFWBase):
    def __init__(self, index, efw=None):
        super().__init__(efw)
        self.handle = -1
        result = self.efw.open(index)
        self._raiseIfBad(result)
        self.handle = index

    def close(self):
        """Closes this device.
        """
        self._assertHandle()
        result = self.efw.close(self.handle)
        self._raiseIfBad(result)
        self.handle = -1

    def isInPosition(self):
        """Returns true if the filter wheel has stopped moving.

        Returns
        -------
        boolean
            True if the filter wheel has stopped moving."""
        return self.getPosition() != -1

    def getPosition(self):
        """Gets the current position of the filter wheel.

        If the reported filter is -1 then that means the device
        is currently moving.

        Returns
        -------
        int
            The current filter (0 based) OR -1 if the filter
            wheel is currently moving."""
        result, position = self.efw.getPosition(self.handle)
        self._raiseIfBad(result)
        return position

    def setPosition(self, position):
        """Sets the current filter to the specified position.

        Parameters
        ----------
        position : int
            The filter to change to."""
        result = self.efw.setPosition(self.handle, position)
        self._raiseIfBad(result)

    def _assertHandle(self):
        if self.handle == -1:
            raise EFWDeviceNotOpenError()
