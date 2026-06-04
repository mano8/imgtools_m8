"""ImgTools_m8 init logger entry."""

import logging

__author__ = "Eli Serra"
__copyright__ = "Copyright 2023, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "2.0.0"

try:
    import colorama

    colorama.init(autoreset=True)
    _COLORAMA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _COLORAMA_AVAILABLE = False
    colorama = None  # type: ignore[assignment]

_LEVEL_COLORS = {
    logging.DEBUG: "\033[36m",  # cyan
    logging.INFO: "\033[32m",  # green
    logging.WARNING: "\033[33m",  # yellow
    logging.ERROR: "\033[31m",  # red
    logging.CRITICAL: "\033[35m",  # magenta
}
_RESET = "\033[0m"


class AppFilter(logging.Filter):
    """Add app_version field to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Logger app version."""
        record.app_version = f"imgTools_m8-{__version__}"
        return True


class _ColorFormatter(logging.Formatter):
    """Wrap each log line in an ANSI color when colorama is available."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with optional color prefix."""
        msg = super().format(record)
        if _COLORAMA_AVAILABLE:
            color = _LEVEL_COLORS.get(record.levelno, "")
            return f"{color}{msg}{_RESET}"
        return msg


def configure_logging(debug: bool = False) -> None:
    """
    Configure the imgTools_m8 logger for CLI/script use.

    Attaches a colored StreamHandler when colorama is available.
    :param debug: If True, set log level to DEBUG.
    """
    logger = logging.getLogger("imgTools_m8")
    if logger.handlers:
        return  # already configured — avoid duplicate handlers
    logger.addFilter(AppFilter())
    logger.propagate = False

    handler = logging.StreamHandler()
    formatter = _ColorFormatter(
        "%(asctime)s.%(msecs)03d :: %(app_version)s :: %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(level)
    handler.setLevel(level)
    logger.addHandler(handler)

    logger.debug("Logger ready. debug=%s colorama=%s", debug, _COLORAMA_AVAILABLE)
