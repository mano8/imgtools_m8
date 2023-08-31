"""ImgTools_m8 init logger entry."""
import logging

__author__ = "Eli Serra"
__copyright__ = "Copyright 2023, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.1.0"


class AppFilter(logging.Filter):
    """
    Class used to add a custom entry into the logger.
    """

    def filter(self, record):
        """Logger app version."""
        record.app_version = "imgTools_m8-%s" % __version__
        return True


def configure_logging(debug: bool = False):
    """
    Prepare log folder in current home directory.

    Format logger output
    :param debug: If true, set the lof level to debug
    """
    logger = logging.getLogger("imgTools_m8")
    logger.addFilter(AppFilter())
    logger.propagate = False
    syslog = logging.StreamHandler()
    syslog.setLevel(logging.INFO)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d :: %(app_version)s :: %(message)s', "%Y-%m-%d %H:%M:%S"
    )
    syslog.setFormatter(formatter)

    if debug:
        logger.setLevel(logging.DEBUG)
        syslog.setLevel(logging.DEBUG)

    # add the handlers to logger
    logger.addHandler(syslog)

    logger.debug("Logger ready. debug : %s", debug)
