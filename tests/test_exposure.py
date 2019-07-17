
import unittest
import tempfile
import numpy as np
import os

from lsst.ts.GenericCamera import Exposure


class TestExposure(unittest.TestCase):

    def test(self):

        width = 1024
        height = 1024
        image = np.random.randint(low=np.iinfo(np.uint8).min,
                                  high=np.iinfo(np.uint8).max,
                                  size=(width, height),
                                  dtype=np.uint8)

        exp = Exposure(buffer=image,
                       width=width,
                       height=height,
                       tags=["unit-test", "test", "unit"])

        tmp_name = os.path.join(tempfile.gettempdir(),
                                f"{next(tempfile._get_candidate_names())}.fits")

        exp.save(tmp_name)

        self.assertTrue(os.path.exists(tmp_name),
                        f"File {tmp_name} doe not exists.")

        exp.makeJPEG()

        self.assertTrue(exp.isJPEG)


if __name__ == "__main__":
    unittest.main()
