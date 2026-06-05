"""
imgtools_m8 example — multiprocess web image pipeline.

Converts all images in the source directory to multiple widths (JPEG + WEBP)
using parallel worker processes.

Usage:
    python examples/multiprocess.py --source ./images --output ./out
    python examples/multiprocess.py --source ./images --output ./out --workers 4
"""

import argparse
import sys

from imgtools_m8 import configure_logging
from imgtools_m8.multiprocess import MultiProcessImage

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "2.0.0"


def parse_args(args):
    """Parse source / output / workers / debug arguments."""
    p = argparse.ArgumentParser(description="imgtools_m8 multiprocess pipeline example")
    p.add_argument("--source", required=True, help="Source file or directory")
    p.add_argument("--output", required=True, help="Output directory")
    p.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes (default: auto)",
    )
    p.add_argument("--debug", action="store_true", help="Show debug output")
    return p.parse_args(args)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    configure_logging(args.debug)

    obj = MultiProcessImage(
        conf={
            "source_path": args.source,
            "output_path": args.output,
            "include_subdirs": True,
            "output_options": [
                {
                    "image_size": {"fixed_width": 2500},
                    "formats": [
                        {
                            "ext": "JPEG",
                            "quality": 95,
                            "progressive": True,
                            "optimize": True,
                        },
                        {"ext": "WEBP", "quality": 80},
                    ],
                },
                {
                    "image_size": {"fixed_width": 1920},
                    "formats": [
                        {
                            "ext": "JPEG",
                            "quality": 95,
                            "progressive": True,
                            "optimize": True,
                        },
                        {"ext": "WEBP", "quality": 80},
                    ],
                },
                {
                    "image_size": {"fixed_width": 1280},
                    "formats": [
                        {
                            "ext": "JPEG",
                            "quality": 95,
                            "progressive": True,
                            "optimize": True,
                        },
                        {"ext": "WEBP", "quality": 80},
                    ],
                },
            ],
        },
        num_processes=args.workers,
        use_progress=True,
    )
    ok = obj.run_multiple()
    sys.exit(0 if ok else 1)
