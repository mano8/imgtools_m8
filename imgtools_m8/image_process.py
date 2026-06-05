"""imagetools_m8 main module."""

import io
import logging
import os
from os.path import basename, isdir, isfile, join, splitext
from typing import TYPE_CHECKING, Optional, Tuple

from PIL import Image, UnidentifiedImageError
from pydantic import TypeAdapter

from imgtools_m8.helpers.file_utils import FileUtils
from imgtools_m8.helpers.scan_dir import ScanDir
from imgtools_m8.schemas.conf_schema import (
    FormatsList,
    ImageProcessingSchema,
    OutputOptions,
    OutputSize,
)

if TYPE_CHECKING:
    from imgtools_m8.img_expander import ImageExpander

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "2.0.0"

try:
    import cv2
    import numpy as np  # pragma: no cover

    from imgtools_m8.img_expander import CV2_AVAILABLE  # pragma: no cover

    DNN_AVAILABLE = CV2_AVAILABLE  # pragma: no cover
except ImportError:  # pragma: no cover
    DNN_AVAILABLE = False
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]

logger = logging.getLogger("imgTools_m8")

_EXT_MAP = {
    "JPEG": ".jpg",
    "WEBP": ".webp",
    "PNG": ".png",
    "GIF": ".gif",
    "AVIF": ".avif",
}


class ImageProcessing:
    """
    The core class for ImgTools_m8 providing image processing functionality.
    """

    def __init__(
        self,
        conf: dict,
        model_conf: Optional[dict] = None,
    ):
        """
        Initialize the ImageProcessing instance.

        Args:
            conf (dict): Processing configuration matching ImageProcessingSchema.
            model_conf (Optional[dict]): DNN upscaling model configuration.
        """
        self.conf = TypeAdapter(ImageProcessingSchema).validate_python(conf)
        self.expander: Optional["ImageExpander"] = None
        if model_conf is not None:
            self._set_expander(model_conf)

    def has_conf(self) -> bool:
        """Check if the instance has a valid configuration."""
        return isinstance(self.conf, ImageProcessingSchema)

    def has_input_file(self) -> bool:
        """Check if source_path is an existing file."""
        return self.has_conf() and isfile(self.conf.source_path)

    def has_input_dir(self) -> bool:
        """Check if source_path is an existing directory."""
        return self.has_conf() and isdir(self.conf.source_path)

    def has_output_options(self) -> bool:
        """Check if output_options list is present."""
        return self.has_conf() and isinstance(self.conf.output_options, list)

    def has_expander(self) -> bool:
        """Check if DNN expander is loaded and ready."""
        return DNN_AVAILABLE and self.expander is not None and self.expander.is_ready()

    def _set_expander(self, model_conf: dict) -> bool:
        """Initialize and load the DNN upscaling model."""
        if not (DNN_AVAILABLE and isinstance(model_conf, dict) and model_conf):
            return False
        from imgtools_m8.img_expander import ImageExpander as _IE  # pragma: no cover

        self.expander = _IE(model_conf=model_conf)  # type: ignore[arg-type]  # pragma: no cover
        if not self.expander.has_model_conf():  # pragma: no cover
            return False  # pragma: no cover
        self.expander.init_sr()  # pragma: no cover
        return self.expander.load_model()  # pragma: no cover

    @staticmethod
    def _get_output_stem(file_name: str, size: Tuple[int, int]) -> str:
        """Build output filename stem from original name and final pixel size."""
        name, _ = splitext(basename(file_name))
        w, h = size
        return f"{name}_{w}x{h}"

    @staticmethod
    def _get_output_subdir(
        output_path: str,
        sub_dirs: Optional[list],
        flatten: bool,
    ) -> str:
        """Resolve output subdirectory, creating it when needed."""
        if flatten or not sub_dirs:
            return output_path
        target = join(output_path, *sub_dirs)
        os.makedirs(target, exist_ok=True)
        return target

    @staticmethod
    def _box_ratio(w: int, h: int, fixed_width: int, fixed_height: int) -> float:
        """Return scale ratio to fit (w, h) inside the bounding box (downscale path)."""
        need_w = fixed_width < w
        need_h = fixed_height < h
        if need_w and not need_h:
            return fixed_width / w
        if need_h and not need_w:
            return fixed_height / h
        pct_w = (w - fixed_width) / w
        pct_h = (h - fixed_height) / h
        return fixed_width / w if pct_w >= pct_h else fixed_height / h

    @staticmethod
    def _fit_within_box(
        w: int,
        h: int,
        fixed_width: int,
        fixed_height: int,
        allow_upscale: bool,
    ) -> Tuple[int, int]:
        """Scale (w, h) to fit inside a fixed_width × fixed_height box."""
        if fixed_width >= w and fixed_height >= h:
            if not allow_upscale:
                return w, h
            scale = min(fixed_width / w, fixed_height / h)
            return max(1, round(w * scale)), max(1, round(h * scale))
        ratio = ImageProcessing._box_ratio(w, h, fixed_width, fixed_height)
        return max(1, round(w * ratio)), max(1, round(h * ratio))

    @staticmethod
    def _compute_fixed_size(
        w: int, h: int, fixed_size: int, allow_upscale: bool
    ) -> Optional[Tuple[int, int]]:
        """Scale (w, h) uniformly so the dominant side equals fixed_size."""
        dominant = max(w, h)
        if not allow_upscale and dominant <= fixed_size:
            return None
        ratio = fixed_size / dominant
        return max(1, round(w * ratio)), max(1, round(h * ratio))

    @staticmethod
    def _compute_fixed_width(
        w: int, h: int, fixed_width: int, allow_upscale: bool
    ) -> Optional[Tuple[int, int]]:
        """Scale to fixed_width, preserving aspect ratio."""
        if not allow_upscale and fixed_width >= w:
            return None
        return fixed_width, max(1, round(h * (fixed_width / w)))

    @staticmethod
    def _compute_fixed_height(
        w: int, h: int, fixed_height: int, allow_upscale: bool
    ) -> Optional[Tuple[int, int]]:
        """Scale to fixed_height, preserving aspect ratio."""
        if not allow_upscale and fixed_height >= h:
            return None
        return max(1, round(w * (fixed_height / h))), fixed_height

    @staticmethod
    def _compute_new_size(
        w: int,
        h: int,
        image_size: OutputSize,
        allow_upscale: bool,
    ) -> Optional[Tuple[int, int]]:
        """Return target (new_w, new_h) from an OutputSize spec, or None for no-op."""
        if image_size.fixed_upscale is not None:
            f = image_size.fixed_upscale
            return w * f, h * f
        if image_size.fixed_downscale is not None:
            f = image_size.fixed_downscale
            return max(1, w // f), max(1, h // f)
        if image_size.fixed_size is not None:
            return ImageProcessing._compute_fixed_size(
                w, h, image_size.fixed_size, allow_upscale
            )
        if image_size.fixed_width is not None:
            if image_size.fixed_height is not None:
                return ImageProcessing._fit_within_box(
                    w, h, image_size.fixed_width, image_size.fixed_height, allow_upscale
                )
            return ImageProcessing._compute_fixed_width(
                w, h, image_size.fixed_width, allow_upscale
            )
        if image_size.fixed_height is not None:
            return ImageProcessing._compute_fixed_height(
                w, h, image_size.fixed_height, allow_upscale
            )
        return None

    @staticmethod
    def _resize_to_fit(
        img: Image.Image,
        image_size: OutputSize,
        allow_upscale: bool = False,
    ) -> Image.Image:
        """Resize image according to an OutputSize spec."""
        w, h = img.size
        new_size = ImageProcessing._compute_new_size(w, h, image_size, allow_upscale)
        if new_size is None or new_size == (w, h):
            return img
        new_w, new_h = new_size
        resampler = (
            Image.Resampling.LANCZOS
            if new_w < w or new_h < h
            else Image.Resampling.BICUBIC
        )
        return img.resize((new_w, new_h), resampler)

    @staticmethod
    def _enforce_max_bytes(
        img: Image.Image,
        format_conf,
        max_byte_size: int,
    ) -> dict:
        """Binary-search quality to fit image under max_byte_size."""
        save_kwargs = {
            k: v
            for k, v in format_conf.model_dump(exclude={"ext"}).items()
            if v is not None
        }
        fmt_val = format_conf.ext.value

        if fmt_val not in ("JPEG", "WEBP", "AVIF"):
            return save_kwargs

        buf = io.BytesIO()
        img.save(buf, format=fmt_val, **save_kwargs)
        if buf.tell() <= max_byte_size:
            return save_kwargs

        lo, hi = 1, save_kwargs.get("quality") or 85
        best = {**save_kwargs, "quality": lo}
        while lo <= hi:
            mid = (lo + hi) // 2
            probe = {**save_kwargs, "quality": mid}
            buf = io.BytesIO()
            img.save(buf, format=fmt_val, **probe)
            if buf.tell() <= max_byte_size:
                best = probe
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    @staticmethod
    def _convert_color_mode(img: Image.Image, fmt_val: str) -> Image.Image:
        """Convert image color mode for the given format when required."""
        if fmt_val == "JPEG" and img.mode not in ("RGB", "L"):
            return img.convert("RGB")
        if fmt_val in ("PNG", "WEBP", "GIF") and img.mode == "CMYK":
            return img.convert("RGB")
        return img

    @staticmethod
    def _write_image_to_format(
        img: Image.Image,
        output_dir: str,
        stem: str,
        format_conf,
        max_byte_size: Optional[int] = None,
    ) -> bool:
        """Save image in a specific format, honouring max_byte_size."""
        fmt_val = format_conf.ext.value
        ext = _EXT_MAP.get(fmt_val, f".{fmt_val.lower()}")
        out_path = join(output_dir, f"{stem}{ext}")

        working = ImageProcessing._convert_color_mode(img, fmt_val)

        try:
            if max_byte_size:
                save_kwargs = ImageProcessing._enforce_max_bytes(
                    working, format_conf, max_byte_size
                )
            else:
                save_kwargs = {
                    k: v
                    for k, v in format_conf.model_dump(exclude={"ext"}).items()
                    if v is not None
                }
            working.save(out_path, format=fmt_val, **save_kwargs)
            logger.debug(
                "[ImageProcessing] Wrote %s (%s)",
                out_path,
                FileUtils.get_file_size_str(out_path),
            )
            return True
        except (IOError, OSError, ValueError) as exc:
            logger.warning("[ImageProcessing] Failed to write %s: %s", out_path, exc)
            return False

    def _dnn_upscale(self, img: Image.Image, factor: int) -> Image.Image:
        """Upscale image using DNN model, falling back to PIL bicubic."""
        if not self.has_expander() or self.expander is None:
            w, h = img.size
            return img.resize((w * factor, h * factor), Image.Resampling.BICUBIC)
        src = img.convert("RGB")  # pragma: no cover
        cv_img = cv2.cvtColor(np.array(src), cv2.COLOR_RGB2BGR)  # type: ignore[union-attr,call-overload]  # pragma: no cover
        upscaled = self.expander.many_image_upscale(
            image=cv_img, nb_upscale=1
        )  # pragma: no cover
        result = Image.fromarray(cv2.cvtColor(upscaled, cv2.COLOR_BGR2RGB))  # type: ignore[call-overload,union-attr]  # pragma: no cover
        if img.mode == "RGBA":  # pragma: no cover
            alpha = img.split()[3].resize(
                result.size, Image.Resampling.LANCZOS
            )  # pragma: no cover
            result.putalpha(alpha)  # pragma: no cover
        return result  # pragma: no cover

    def _resolve_formats_and_bytes(self, option: OutputOptions):
        """Return (formats, max_bytes) for an option, falling back to global_options."""
        formats = option.formats
        max_bytes = option.max_byte_size
        if self.conf.global_options is not None:
            if formats is None:
                formats = self.conf.global_options.formats
            if max_bytes is None:
                max_bytes = self.conf.global_options.max_byte_size
        return formats, max_bytes

    def _apply_resize(self, image: Image.Image, option: OutputOptions) -> Image.Image:
        """Apply resize (DNN or PIL) for one output option."""
        if not isinstance(option.image_size, OutputSize):
            return image
        if option.image_size.fixed_upscale is not None and self.has_expander():
            return self._dnn_upscale(  # pragma: no cover
                image,
                option.image_size.fixed_upscale,  # pragma: no cover
            )  # pragma: no cover
        return ImageProcessing._resize_to_fit(
            image, option.image_size, option.allow_upscale or False
        )

    def _write_option_formats(
        self,
        working: Image.Image,
        file_name: str,
        output_dir: str,
        option: OutputOptions,
    ) -> bool:
        """Write all formats for one output option; return True if any succeeded."""
        stem = ImageProcessing._get_output_stem(file_name, working.size)
        formats, max_bytes = self._resolve_formats_and_bytes(option)
        if not formats:  # pragma: no cover
            return False  # pragma: no cover
        result = False
        for fmt_conf in formats:
            if ImageProcessing._write_image_to_format(
                working, output_dir, stem, fmt_conf, max_bytes
            ):
                result = True
        return result

    def process_output_options(
        self,
        image: Image.Image,
        file_name: str,
        output_dir: str,
    ) -> bool:
        """Process all output options (resize + format conversion) for one image."""
        if not self.has_output_options():
            return False
        output_options = self.conf.output_options
        if not isinstance(output_options, list):  # pragma: no cover
            return False  # pragma: no cover
        result = False
        for option in output_options:
            working = self._apply_resize(image, option)
            if self._write_option_formats(working, file_name, output_dir, option):
                result = True
        return result

    def process_file(self, source_path: str, info: dict) -> bool:
        """Open, resize, and convert a single image file."""
        if not isfile(source_path):
            return False
        file_name = info.get("name", basename(source_path))
        sub_dirs = info.get("sub_dirs")
        output_dir = ImageProcessing._get_output_subdir(
            self.conf.output_path,
            sub_dirs,
            self.conf.flatten_output or False,
        )
        try:
            with Image.open(source_path) as img:
                img.load()
                return self.process_output_options(
                    image=img,
                    file_name=file_name,
                    output_dir=output_dir,
                )
        except (IOError, OSError, UnidentifiedImageError) as exc:
            logger.warning("[ImageProcessing] Cannot open %s: %s", source_path, exc)
            return False

    def _iter_source_files(self, ordered: dict):
        """Yield (full_path, file_data) for every file in an ordered-files dict."""
        for _fmt, group in ordered.items():
            raw_root = group.get("root_dir")
            root_dir: str = (
                raw_root if isinstance(raw_root, str) else self.conf.source_path
            )
            for file_data in group.get("files") or []:
                if not isinstance(file_data, dict):  # pragma: no cover
                    continue  # pragma: no cover
                name = file_data.get("name", "")
                sub_dirs = file_data.get("sub_dirs")
                full_path = (
                    join(root_dir, *sub_dirs, name)
                    if isinstance(sub_dirs, list) and sub_dirs
                    else join(root_dir, name)
                )
                yield full_path, file_data

    def process_directory(self) -> bool:
        """Process all images in the configured source directory."""
        if not self.has_input_dir():
            return False
        ordered = ScanDir.get_ordered_files(
            source_path=self.conf.source_path,
            include_subdirs=self.conf.include_subdirs or False,
            byte_size=True,
            image_size=True,
        )
        if not isinstance(ordered, dict):  # pragma: no cover
            return False  # pragma: no cover
        result = False
        for full_path, file_data in self._iter_source_files(ordered):
            if self.process_file(source_path=full_path, info=file_data):
                result = True
        return result

    def run(self) -> bool:
        """Run image processing on the configured source."""
        if not self.has_conf():  # pragma: no cover
            return False  # pragma: no cover
        os.makedirs(self.conf.output_path, exist_ok=True)
        if self.has_input_file():
            info: dict = ScanDir.get_file_item_info(self.conf.source_path) or {}
            info["name"] = basename(self.conf.source_path)
            info.setdefault("sub_dirs", None)
            return self.process_file(source_path=self.conf.source_path, info=info)
        if self.has_input_dir():
            return self.process_directory()
        logger.error(
            "[ImageProcessing] source_path not found: %s",
            self.conf.source_path,
        )
        return False

    @staticmethod
    def has_output_option(
        output_option: Optional[OutputOptions] = None,
    ) -> bool:
        """Check if output_option is a valid OutputOptions instance."""
        return isinstance(output_option, OutputOptions)

    @staticmethod
    def has_image_sizes(
        output_option: Optional[OutputOptions] = None,
    ) -> bool:
        """Check if output_option has a valid image_size constraint."""
        return isinstance(output_option, OutputOptions) and isinstance(
            output_option.image_size, OutputSize
        )

    @staticmethod
    def has_max_bytes(
        output_option: Optional[OutputOptions] = None,
    ) -> bool:
        """Check if output_option has a positive max_byte_size."""
        return (
            isinstance(output_option, OutputOptions)
            and output_option.max_byte_size is not None
            and output_option.max_byte_size > 0
        )

    @staticmethod
    def has_output_formats(
        output_option: Optional[OutputOptions] = None,
    ) -> bool:
        """Check if output_option has a formats list."""
        return isinstance(output_option, OutputOptions) and isinstance(
            output_option.formats, list
        )

    @staticmethod
    def has_output_format(
        output_format=None,
    ) -> bool:
        """Check if output_format is a valid format config instance."""
        return isinstance(output_format, FormatsList)
