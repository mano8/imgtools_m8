"""
ImageTools unittest class.

Use pytest package.
"""
import logging
import argparse
import sys
from imgtools_m8 import configure_logging
from imgtools_m8.multiprocess import MultiProcessImage

logging.basicConfig()
logger = logging.getLogger("imgtools_m8")

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
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
    arg_parser.add_argument('--source', help='Source file or directory', required=True, type=str)
    arg_parser.add_argument('--output_path', help='Output path directory', required=True, type=str)
    arg_parser.add_argument('--debug', action='store_true', help='Show debug output')

    # parse arguments from script parameters
    return arg_parser.parse_args(args)


if __name__ == '__main__':

    parser = parse_args(sys.argv[1:])

    configure_logging(parser.debug)

    source_path = parser.source
    output_conf = {
        'path': parser.output_path,
        'output_formats': [
            {
                'fixed_width': 2500,
                'formats': [
                    {'ext': '.jpg', 'quality': 95, 'progressive': 1, 'optimize': 1},
                    {'ext': '.webp', 'quality': 80}
                ]
            },
            {
                'fixed_width': 2240,
                'formats': [
                    {'ext': '.jpg', 'quality': 95, 'progressive': 1, 'optimize': 1},
                    {'ext': '.webp', 'quality': 80}
                ]
            },
            {
                'fixed_width': 1920,
                'formats': [
                    {'ext': '.jpg', 'quality': 95, 'progressive': 1, 'optimize': 1},
                    {'ext': '.webp', 'quality': 80}
                ]
            },
            {
                'fixed_width': 1280,
                'formats': [
                    {'ext': '.jpg', 'quality': 95, 'progressive': 1, 'optimize': 1},
                    {'ext': '.webp', 'quality': 80}
                ]
            }
        ]

    }
    i_tool = MultiProcessImage(
        source_path=source_path,
        output_conf=output_conf
    )
    i_tool.run_multiple()
