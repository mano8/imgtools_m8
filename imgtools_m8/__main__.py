"""
CLI entry point for imgtools_m8.

Usage:
    imgtools --source ./images --output ./out --format webp:80 --format jpg:95
    imgtools --source ./images --output ./out --width 1920 --format webp:80
    imgtools --source ./images --output ./out --workers 4
    imgtools --source ./images --output ./out --config ./conf.json
"""
import argparse
import json
import logging
import multiprocessing
import sys
from typing import Optional

from imgtools_m8 import configure_logging

logger = logging.getLogger("imgTools_m8")

_EXT_ALIASES: dict[str, str] = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "webp": "WEBP",
    "png": "PNG",
    "gif": "GIF",
    "avif": "AVIF",
}


def _parse_format(spec: str) -> dict:
    """Parse 'webp:80' or 'jpg' into a FormatConfig dict."""
    parts = spec.split(":", 1)
    ext = _EXT_ALIASES.get(parts[0].lower(), parts[0].upper())
    fmt: dict = {"ext": ext}
    if len(parts) == 2:
        try:
            fmt["quality"] = int(parts[1])
        except ValueError:
            logger.warning("Invalid quality value in '%s'; ignoring.", spec)
    return fmt


def _build_image_size(args: argparse.Namespace) -> Optional[dict]:
    """Build an image_size dict from CLI resize flags, or None if none given."""
    size: dict = {}
    if args.width:
        size["fixed_width"] = args.width
    if args.height:
        size["fixed_height"] = args.height
    if args.size:
        size["fixed_size"] = args.size
    if args.downscale:
        size["fixed_downscale"] = args.downscale
    if args.upscale:
        size["fixed_upscale"] = args.upscale
    return size or None


def _build_conf(args: argparse.Namespace) -> dict:
    """Build the ImageProcessingSchema conf dict from parsed CLI args."""
    if args.config:
        try:
            with open(args.config) as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Cannot load config file '%s': %s", args.config, exc)
            sys.exit(1)

    option: dict = {}
    image_size = _build_image_size(args)
    if image_size:
        option["image_size"] = image_size
    if args.allow_upscale:
        option["allow_upscale"] = True
    if args.max_bytes:
        option["max_byte_size"] = args.max_bytes
    formats = [_parse_format(f) for f in args.format] if args.format else []
    option["formats"] = formats or [{"ext": "WEBP", "quality": 80}]

    return {
        "source_path": args.source,
        "output_path": args.output,
        "include_subdirs": args.subdirs,
        "flatten_output": args.flatten,
        "output_options": [option],
    }


def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="imgtools",
        description=(
            "Convert, resize, and batch-process images.\n\n"
            "Format spec: EXT[:QUALITY]  e.g. webp:80  jpg:95  png"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--source", "-s", required=True, help="Source file or directory")
    p.add_argument("--output", "-o", required=True, help="Output directory")

    resize = p.add_argument_group("resize")
    resize.add_argument("--width", "-W", type=int, metavar="N",
                        help="Fixed output width (keeps aspect ratio)")
    resize.add_argument("--height", "-H", type=int, metavar="N",
                        help="Fixed output height (keeps aspect ratio)")
    resize.add_argument("--size", type=int, metavar="N",
                        help="Constrain longest side to N pixels")
    resize.add_argument("--downscale", type=int, metavar="N",
                        help="Divide dimensions by N (2-10)")
    resize.add_argument("--upscale", type=int, metavar="N",
                        help="Multiply dimensions by N (2-10); DNN when [dnn] installed")
    resize.add_argument("--allow-upscale", dest="allow_upscale", action="store_true",
                        help="Allow upscaling with width/height/size constraints")

    out = p.add_argument_group("output")
    out.add_argument("--format", "-f", action="append", metavar="EXT[:QUALITY]",
                     help="Output format, repeatable (default: webp:80)")
    out.add_argument("--max-bytes", dest="max_bytes", type=int, metavar="N",
                     help="Hard byte ceiling per output file")

    scan = p.add_argument_group("source scanning")
    scan.add_argument("--subdirs", action="store_true",
                      help="Scan subdirectories recursively")
    scan.add_argument("--flatten", action="store_true",
                      help="Write all outputs flat (no subdir mirroring)")

    run = p.add_argument_group("processing")
    cpu_max = max(1, multiprocessing.cpu_count() - 1)
    run.add_argument(
        "--workers", type=int, metavar="N",
        help=(
            f"Use multiprocessing with N workers (max {cpu_max} on this machine). "
            "Omit for single-process mode."
        ),
    )
    run.add_argument("--config", metavar="PATH",
                     help="Load full conf dict from a JSON file (overrides other flags)")
    run.add_argument("--debug", action="store_true", help="Enable debug logging")
    return p


def main(argv: Optional[list] = None) -> int:
    """CLI entry point. Returns 0 on success, 1 on failure."""
    parser = _make_parser()
    args = parser.parse_args(argv)
    configure_logging(args.debug)

    conf = _build_conf(args)

    try:
        if args.workers:
            from imgtools_m8.multiprocess import MultiProcessImage

            processor = MultiProcessImage(
                conf=conf,
                use_progress=True,
                num_processes=args.workers,
            )
            ok = processor.run_multiple()
        else:
            from imgtools_m8.image_process import ImageProcessing

            ok = ImageProcessing(conf=conf).run()
    except Exception as exc:
        logger.error("Processing failed: %s", exc)
        return 1

    if ok:
        logger.info("Done.")
    else:
        logger.error("Processing completed with errors.")
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
