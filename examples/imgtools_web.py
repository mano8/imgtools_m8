"""
imgtools_m8 example — single-process web image pipeline.

Converts all images in the source directory to 1920 px and 1280 px wide
WEBP at 95% quality and saves them to the output directory.

Usage:
    python examples/imgtools_web.py --source ./images --output ./out
    python examples/imgtools_web.py  # uses examples/source and examples/output
"""

import argparse
import sys
from os import path

from imgtools_m8 import configure_logging
from imgtools_m8.image_process import ImageProcessing

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "2.0.0"


def parse_args(args):
    """Parse source / output / debug arguments."""
    p = argparse.ArgumentParser(description="imgtools_m8 web pipeline example")
    p.add_argument("--source", help="Source file or directory", type=str)
    p.add_argument("--output", help="Output directory", type=str)
    p.add_argument("--debug", action="store_true", help="Show debug output")
    return p.parse_args(args)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    configure_logging(args.debug)

    source = args.source or path.join(path.dirname(__file__), "source")
    output = args.output or path.join(path.dirname(__file__), "output")

    obj = ImageProcessing(
        conf={
            "source_path": source,
            "output_path": output,
            "include_subdirs": True,
            "output_options": [
                {
                    "image_size": {"fixed_width": 1920},
                    "formats": [{"ext": "WEBP", "quality": 95}],
                },
                {
                    "image_size": {"fixed_width": 1280},
                    "formats": [{"ext": "WEBP", "quality": 95}],
                },
            ],
        }
    )
    ok = obj.run()
    sys.exit(0 if ok else 1)
