"""
ImageTools Example.
Resize all images from source path to sizes:
  - 1280px width
  - 1920px width
All images are converted to JPEG and WEBP format with 95% quality,
and saved to output path.

Depending on source files, images sizes will be upscale and/or downscale.
"""
import logging
import argparse
import sys
from os import path
from imgtools_m8 import configure_logging
from imgtools_m8.img_tools import ImageTools


logging.basicConfig()
logger = logging.getLogger("imgtools_m8")

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "1.0.0"


def parse_args(args):
    """
    Parsing function.

    Parse arguments used in example
    :param args: arguments passed from the command line
    :return: return parser
    """
    # create arguments
    arg_parser = argparse.ArgumentParser(description='imgtools_m8 example')
    arg_parser.add_argument('--source', help='Source file or directory', type=str)
    arg_parser.add_argument('--output_path', help='Output path directory', type=str)
    arg_parser.add_argument('--debug', action='store_true', help='Show debug output')

    # parse arguments from script parameters
    return arg_parser.parse_args(args)


if __name__ == '__main__':

    parser = parse_args(sys.argv[1:])

    configure_logging(parser.debug)

    source_path = parser.source
    if source_path is None:
        source_path = path.join(path.dirname(__file__), 'source')
    output_path = parser.output_path
    if output_path is None:
        output_path = path.join(path.dirname(__file__), 'output')

    output_formats = [
        {
            'fixed_width': 1920,
            'formats': [
                {'ext': '.jpg', 'quality': 95, 'progressive': 1, 'optimize': 1},
                {'ext': '.webp', 'quality': 95}
            ]
        },
        {
            'fixed_width': 1280,
            'formats': [
                {'ext': '.jpg', 'quality': 95, 'progressive': 1, 'optimize': 1},
                {'ext': '.webp', 'quality': 95}
            ]
        }
    ]

    i_tool = ImageTools(
        source_path=source_path,
        output_path=output_path,
        output_formats=output_formats
    )
    i_tool.run()
