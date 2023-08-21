"""
ImgTools_m8 core class.
"""
import cv2
from numpy import ndarray
import os
import logging
from ve_utils.utils import UType as Ut
from imgtools_m8.helper import ImageToolsHelper
from imgtools_m8.process_conf import ProcessConf
from imgtools_m8.img_expander import ImageExpander
from imgtools_m8.exceptions import ImgToolsException
from imgtools_m8.exceptions import SettingInvalidException

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "2.0.0"

logging.basicConfig()
logger = logging.getLogger("imgTools_m8")


class ImageTools:
    """
        ImageTools
    """
    def __init__(self,
                 source_path: str,
                 output_path: str,
                 output_formats: list,
                 model_conf: dict or None = None,
                 ):
        self.expander = None
        self.model_conf = model_conf
        self.conf = None
        self.set_conf(
            source_path=source_path,
            output_path=output_path,
            output_formats=output_formats
        )

    def is_ready(self) -> bool:
        """Test if is_ready"""
        return self.has_conf()

    def has_expander(self) -> bool:
        """Test if is_ready"""
        return isinstance(self.expander, ImageExpander)

    def init_expander(self):
        """Test if is_ready"""
        if not self.has_expander():
            self.expander = ImageExpander(model_conf=self.model_conf)

    def has_expander_model(self) -> bool:
        """Test if is_ready"""
        return self.has_expander() and self.expander.is_ready()

    def init_expander_model(self):
        """Test if is_ready"""
        self.init_expander()
        if not self.has_expander_model():
            self.expander.init_sr()
            self.expander.load_model()

    def get_model_scale(self) -> int:
        """Get model scale value"""
        result = 0
        self.init_expander()
        if self.has_expander():
            result = self.expander.model_conf.get_scale()
        return result

    def get_available_model_scales(self) -> list:
        """Get model scale value"""
        result = []
        self.init_expander()
        if self.has_expander():
            result = self.expander.model_conf.get_available_scales()
        return result

    def has_conf(self) -> bool:
        """Test if instance has valid configuration"""
        return isinstance(self.conf, ProcessConf) \
            and self.conf.is_ready()

    def set_source_path(self, source_path: str) -> bool:
        """
        Set source_path property.
        Can be a directory or image path.
        """
        return self.conf.set_source_path(source_path)

    def set_output_path(self, output_path: str) -> bool:
        """
        Set output_path property.
        """
        return self.conf.set_output_path(output_path)

    def set_output_formats(self, output_formats: list) -> bool:
        """
        Set output_formats property.
        """
        return self.conf.set_output_formats(output_formats)

    def set_conf(self,
                 source_path: str,
                 output_path: str,
                 output_formats: list
                 ) -> bool:
        """Set process configuration."""
        self.conf = ProcessConf(
            source_path=source_path,
            output_path=output_path,
            output_formats=output_formats
        )
        return self.conf.is_ready()

    def resize_need(self,
                    image: ndarray,
                    output_format: dict
                    ) -> ndarray or None:
        """Set image output path file"""
        result = None
        if image is not None:
            size = ImageToolsHelper.get_image_size(image)
            params = ImageTools.get_downscale_size(
                size=size,
                fixed_height=output_format.get('fixed_height'),
                fixed_width=output_format.get('fixed_width')
            )
            if params is not None:
                result = self.image_resize(
                    image=image,
                    **params
                )
            else:
                return image
        return result

    def upscale_image(self,
                      image: ndarray,
                      size: tuple,
                      upscale_stats: dict,
                      file_name: str
                      ) -> ndarray or None:
        """Resize image from output configuration"""
        result = False
        if image is not None \
                and Ut.is_tuple(size) \
                and Ut.is_dict(upscale_stats, not_null=True) \
                and Ut.is_list(upscale_stats.get('stats'), not_null=True):
            output_formats = self.conf.get_output_formats()
            upscale_counter = 0
            result = True
            self.init_expander_model()
            for upscale in upscale_stats.get('stats'):
                key = upscale.get('key')
                nb_upscale = upscale.get('nb_upscale')
                output_format = output_formats[key]
                if nb_upscale > 0:
                    if nb_upscale > upscale_counter:
                        logger.debug(
                            "[ImageTools] Image upscale %s / %s -> %sx",
                            upscale_counter,
                            nb_upscale,
                            self.get_model_scale()
                        )
                        nb_upscale_needed = nb_upscale - upscale_counter
                        image = self.expander.many_image_upscale(
                            image=image,
                            nb_upscale=nb_upscale_needed
                        )
                        upscale_counter = nb_upscale
                    resized = self.resize_need(
                        image=image,
                        output_format=output_format
                    )
                else:
                    resized = self.resize_need(
                        image=image,
                        output_format=output_format
                    )

                if not ImageTools.write_images_by_format(
                        image=resized,
                        output_path=self.conf.get_output_path(),
                        file_name=file_name,
                        output_format=output_format.get('formats')):
                    result = False
        return result

    def downscale_or_convert_image(self,
                                   image: ndarray,
                                   size: tuple,
                                   file_name: str
                                   ) -> ndarray or None:
        """Downscale or convert image"""
        result = False
        if image is not None \
                and Ut.is_tuple(size):
            resized = image
            result = True
            for output_format in self.conf.get_output_formats():
                resized = self.resize_need(
                    image=resized,
                    output_format=output_format
                )
                if not ImageTools.write_images_by_format(
                        image=resized,
                        output_path=self.conf.get_output_path(),
                        file_name=file_name,
                        output_format=output_format.get('formats')):
                    result = False
        return result

    def resize_image_from_conf(self,
                               image: ndarray,
                               size: tuple,
                               upscale_stats: dict,
                               file_name: str
                               ) -> ndarray or None:
        """Resize image from output configuration"""
        result = False
        if image is not None \
                and Ut.is_tuple(size) \
                and Ut.is_dict(upscale_stats, not_null=True)\
                and Ut.is_list(upscale_stats.get('stats'), not_null=True):
            # if upscale needed
            if upscale_stats.get('max_upscale') > 0:
                logger.debug(
                    "[ImageTools] Image need upscale %s times (%sx)",
                    upscale_stats.get('max_upscale'),
                    self.get_model_scale()
                )
                result = self.upscale_image(
                    image=image,
                    size=size,
                    upscale_stats=upscale_stats,
                    file_name=file_name
                )
            # if only downscale or convert image needed
            else:
                logger.debug(
                    "[ImageTools] Image need downscale or conversion."
                )
                result = self.downscale_or_convert_image(
                    image=image,
                    size=size,
                    file_name=file_name
                )
        return result

    def process_image(self,
                      source_path: str,
                      file_name: str
                      ) -> bool:
        """Process Image"""
        result = False
        if self.is_ready() \
                and os.path.isfile(source_path) \
                and Ut.is_str(file_name):
            image = cv2.imread(source_path)
            logger.debug(
                "[ImageTools] Open image : %s (size: %s)",
                source_path,
                ImageToolsHelper.get_string_file_size(
                    source_path=source_path
                )
            )
            if image is not None:
                size = ImageToolsHelper.get_image_size(image)
                upscale_stats = ImageToolsHelper.get_upscale_stats(
                    size=size,
                    output_formats=self.conf.get_output_formats(),
                    model_scale=self.get_model_scale(),
                    # available_scales=self.get_available_model_scales()
                )
                result = self.resize_image_from_conf(
                    image=image,
                    size=size,
                    upscale_stats=upscale_stats,
                    file_name=file_name
                )
            else:
                logger.warning(
                    "[ImageTools] Bad image file : %s (size: %s)",
                    source_path,
                    ImageToolsHelper.get_string_file_size(
                        source_path=source_path
                    )
                )
        return result

    def run(self):
        """Run image enlarger"""
        result = False
        if self.is_ready():
            if os.path.isfile(self.conf.get_source_path()):
                file = os.path.basename(self.conf.get_source_path())
                if self.process_image(
                        source_path=self.conf.get_source_path(),
                        file_name=file
                        ):
                    result = True
            elif os.path.isdir(self.conf.get_source_path()):
                files = ImageToolsHelper.get_images_list(self.conf.get_source_path())
                if Ut.is_list(files, not_null=True):
                    result = True
                    for file in files:
                        if not self.process_image(
                                    source_path=os.path.join(self.conf.get_source_path(), file),
                                    file_name=file
                                ):
                            result = False
        return result

    @staticmethod
    def get_downscale_size(size: tuple,
                           fixed_height: int,
                           fixed_width: int,
                           ) -> dict or None:
        """Get downscale image size"""
        result = None
        if Ut.is_tuple(size, not_null=True) \
                and Ut.is_int(size[0], mini=1) \
                and Ut.is_int(size[1], mini=1):
            h, w = size
            if Ut.is_int(fixed_width, not_null=True) \
                    and Ut.is_int(fixed_height, not_null=True) \
                    and (fixed_width < w
                         or fixed_height < h):
                percent_w = ((w-fixed_width) * 100) / w
                percent_h = ((h-fixed_height) * 100) / h
                is_resize_all = fixed_height < h \
                    and fixed_width < w
                if (fixed_width < w
                        and fixed_height >= h) \
                        or (is_resize_all
                            and percent_w >= percent_h):
                    result = {'width': fixed_width}
                elif (fixed_height < h
                        and fixed_width >= w) \
                        or (is_resize_all
                            and percent_w <= percent_h):
                    result = {'height': fixed_height}
            elif Ut.is_int(fixed_height, not_null=True) \
                    and fixed_height < h:
                result = {'height': fixed_height}
            elif Ut.is_int(fixed_width, not_null=True) \
                    and fixed_width < w:
                result = {'width': fixed_width}
        return result

    @staticmethod
    def read_image(source_path: str) -> ndarray or None:
        """Init sr"""
        img_src = None
        if Ut.is_str(source_path, not_null=True) \
                and os.path.isfile(source_path):
            img_src = cv2.imread(source_path)
        return img_src

    @staticmethod
    def set_write_path(output_path: str,
                       file_name: str,
                       ext: str,
                       size: tuple
                       ):
        """Set image output path file name"""
        result = None
        name, old_ext = ImageToolsHelper.cut_file_name(file_name)
        if Ut.is_str(name, not_null=True) \
                and Ut.is_tuple(size) \
                and len(size) == 2 \
                and Ut.is_str(ext, not_null=True)\
                and os.path.isdir(output_path):
            image_name = "%s_%sx%s%s" % (name, size[1], size[0], ext)
            result = os.path.join(output_path, image_name)
        return result

    @staticmethod
    def get_jpeg_write_options(output_format: dict) -> list or None:
        """Get jpeg write options"""
        result = []
        if Ut.is_int(output_format.get('quality')):
            result.append(cv2.IMWRITE_JPEG_QUALITY)
            result.append(output_format.get('quality'))

        if Ut.is_int(output_format.get('progressive')):
            result.append(cv2.IMWRITE_JPEG_PROGRESSIVE)
            result.append(output_format.get('progressive'))

        if Ut.is_int(output_format.get('optimize')):
            result.append(cv2.IMWRITE_JPEG_OPTIMIZE)
            result.append(output_format.get('optimize'))

        if not Ut.is_list(result, not_null=True):
            result = None
        return result

    @staticmethod
    def get_webp_write_options(output_format: dict) -> list or None:
        """Get webp write options"""
        result = []
        if Ut.is_int(output_format.get('quality')):
            result.append(cv2.IMWRITE_WEBP_QUALITY)
            result.append(output_format.get('quality'))

        if not Ut.is_list(result, not_null=True):
            result = None
        return result

    @staticmethod
    def get_png_write_options(output_format: dict) -> list or None:
        """Get png write options"""
        result = []
        if Ut.is_int(output_format.get('compression')):
            result.append(cv2.IMWRITE_PNG_COMPRESSION)
            result.append(output_format.get('compression'))

        if not Ut.is_list(result, not_null=True):
            result = None
        return result

    @staticmethod
    def write_image_format(image: ndarray or None,
                           output_path: str,
                           file_name: str,
                           output_format: dict
                           ) -> bool:
        """Write image to defined format"""
        result = False
        if ProcessConf.is_output_write_formats(output_format):
            ext = output_format.get('ext')
            options = None
            if ProcessConf.is_output_write_jpg_format(output_format):
                options = ImageTools.get_jpeg_write_options(output_format)
            elif ProcessConf.is_output_write_webp_format(output_format):
                options = ImageTools.get_webp_write_options(output_format)
            elif ProcessConf.is_output_write_png_format(output_format):
                options = ImageTools.get_png_write_options(output_format)

            result = ImageTools.write_image(
                image=image,
                output_path=output_path,
                file_name=file_name,
                ext=ext,
                options=options
            )
        return result

    @staticmethod
    def write_images_by_format(image: ndarray or None,
                               output_path: str,
                               file_name: str,
                               output_format: list
                               ) -> bool:
        """Write images to defined format"""
        result = False
        if Ut.is_list(output_format, not_null=True):
            result = True
            for write_format in output_format:
                if not ImageTools.write_image_format(
                        image=image,
                        output_path=output_path,
                        file_name=file_name,
                        output_format=write_format
                        ):
                    result = False
        return result

    @staticmethod
    def write_image(image: ndarray or None,
                    output_path: str,
                    file_name: str,
                    ext: str,
                    options: list or None = None
                    ) -> ndarray or None:
        """Init sr"""
        out_path = ImageTools.set_write_path(
            output_path=output_path,
            file_name=file_name,
            ext=ext,
            size=ImageToolsHelper.get_image_size(image)
        )
        if image is not None and out_path is not None:
            # Save the image
            if Ut.is_list(options, not_null=True):
                result = cv2.imwrite(out_path, image, options)
            else:
                result = cv2.imwrite(out_path, image)

            logger.debug(
                "[ImageTools] Write image %s (size: %s)",
                out_path,
                ImageToolsHelper.get_string_file_size(
                    source_path=out_path
                )
            )
        else:
            raise ImgToolsException(
                "Unable to resize the image."
            )
        return result

    @staticmethod
    def image_resize(image: ndarray,
                     width: int or float or None = None,
                     height: int or float or None = None,
                     inter=cv2.INTER_AREA
                     ) -> ndarray or None:
        """Resize an image"""
        # initialize the dimensions of the image to be resized and
        # grab the image size
        h, w = ImageToolsHelper.get_image_size(image)

        # if both the width and height are None, then return the
        # original image
        if width is None and height is None:
            logger.debug(
                "[ImageTools] Image no need to be resized."
            )
            return image

        # check to see if the width is None
        if width is None \
                and Ut.is_int(h, not_null=True) \
                and height <= h:
            # calculate the ratio of the height and construct the
            # dimensions
            r = height / float(h)
            dim = (int(w * r), height)

        # otherwise, the height is None
        elif height is None \
                and Ut.is_int(w, not_null=True) \
                and width <= w:
            # calculate the ratio of the width and construct the
            # dimensions
            r = width / float(w)
            dim = (width, int(h * r))

        else:
            raise ImgToolsException(
                "[ImageTools::image_resize] "
                "Error: Unable to resize image, bad sizes."
            )
        resized = None
        if dim is not None:
            # resize the image
            logger.debug(
                "[ImageTools] Resize image from %s x %s to %s x %s pix",
                w,
                h,
                dim[1],
                dim[0]
            )
            resized = cv2.resize(image, dsize=dim, interpolation=inter)

        # return the resized image
        return resized
