"""
ImgTools_m8 multiprocessing class.
"""
import logging
import multiprocessing
import time
import os
from ve_utils.utils import UType as Ut
from imgtools_m8.helper import ImageToolsHelper
from imgtools_m8.img_tools import ImageTools

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.0.0"

logging.basicConfig()
logger = logging.getLogger("imgTools_m8")


class MultiProcessImage(ImageTools):
    """
        MultiProcessing ImageTools
    """

    def __init__(self,
                 source_path: str,
                 output_path: str,
                 output_formats: list,
                 model_conf: dict or None = None,
                 ):
        ImageTools.__init__(self,
                            source_path=source_path,
                            output_path=output_path,
                            output_formats=output_formats,
                            model_conf=model_conf
                            )

    def run_multiple(self) -> bool:
        """Run from directory with multiprocessing"""
        result = False
        start_time = time.time()
        files = ImageToolsHelper.get_images_list(self.conf.get_source_path())
        if self.has_conf() \
                and Ut.is_list(files, not_null=True) \
                and os.path.isdir(self.conf.get_source_path()):
            cpu_count = multiprocessing.cpu_count()
            pool = multiprocessing.Pool(processes=cpu_count)
            try:
                prms = list()
                for file in files:
                    prms.append((
                        os.path.join(self.conf.get_source_path(), file),
                        file
                    ))
                # Multi Process Images
                result = pool.starmap(self.process_image, prms)
                if False in result:
                    result = False
                else:
                    result = True
            finally:
                pool.close()
                pool.join()

        logger.debug(
            "Processing time %s sec",
            time.time() - start_time
        )
        return result
