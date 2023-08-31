"""
ImgTools_m8 core class.
"""
import time
import cv2
from numpy import ndarray
import os
import logging
from ve_utils.utils import UType as Ut
from imgtools_m8.helper import ImageToolsHelper
from imgtools_m8.model_scale_selector import ModelScaleSelector
from imgtools_m8.process_conf import ProcessConf
from imgtools_m8.img_expander import ImageExpander
from imgtools_m8.model_conf import ScaleSelector
from imgtools_m8.exceptions import ImgToolsException

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
    The core class for ImgTools_m8 providing image processing functionality.
    """
    def __init__(self,
                 source_path: str,
                 output_path: str,
                 output_formats: list,
                 model_conf: dict or None = None,
                 ):
        """
                Initialize the ImageTools instance.

                :param source_path: The path to the source image or directory.
                :type source_path: str
                :param output_path: The path to the output directory.
                :type output_path: str
                :param output_formats: A list of output format configurations.
                :type output_formats: list
                :param model_conf: The model configuration dictionary.
                :type model_conf: dict, optional

                Example:
                    >>> source_path = 'input_images'
                    >>> output_path = 'output_images'
                    >>> output_formats = [{'ext': '.jpg', 'quality': 90}]
                    >>> model_conf = {'path': 'models', 'model_name': 'edsr', 'scale': 2}
                    >>> img_tools = ImageTools(source_path, output_path, output_formats, model_conf)
                """
        self.expander = None
        self.conf = None
        self.set_expander(model_conf)
        self.set_conf(
            source_path=source_path,
            output_path=output_path,
            output_formats=output_formats
        )

    def is_ready(self) -> bool:
        """
        Test if the ImageTools instance is ready for processing.

        :return: True if the instance is ready, False otherwise.
        :rtype: bool

        Example:
            >>> tools = ImageTools(...)
            >>> tools.is_ready()
            True
        """
        return self.has_conf()

    def has_expander(self) -> bool:
        """
        Check if the instance has an initialized ImageExpander.

        :return: True if an ImageExpander instance is present, False otherwise.
        :rtype: bool

        Example:
            >>> tools = ImageTools(...)
            >>> tools.has_expander()
            False
        """
        return isinstance(self.expander, ImageExpander)

    def set_expander(self, model_conf: dict or None) -> bool:
        """
        Set the image expander using the provided model configuration.

        :param model_conf: The model configuration dictionary.
        :type model_conf: dict or None

        :return: True if the expander was successfully set, False otherwise.
        :rtype: bool

        Example:
            >>> model_configuration = {'scale': 2}
            >>> tools = ImageTools(...)
            >>> result = tools.set_expander(model_conf=model_configuration)
            >>> print(result)  # Output: True
        """
        result = False
        if Ut.is_dict(model_conf):
            self.expander = ImageExpander(model_conf=model_conf)
            result = True
        return result

    def init_expander(self):
        """
        Initialize the ImageExpander if not already initialized.

        Example:
            >>> tools = ImageTools(...)
            >>> tools.init_expander()
        """
        if not self.has_expander():
            self.expander = ImageExpander()

    def has_expander_model(self) -> bool:
        """
        Check if the ImageExpander instance is ready with a loaded model.

        :return: True if the ImageExpander instance is ready with a loaded model, False otherwise.
        :rtype: bool

        Example:
            >>> tools = ImageTools(...)
            >>> tools.init_expander_model()
            >>> tools.has_expander_model()
            True
        """
        return self.has_expander() and self.expander.is_ready()

    def init_expander_model(self):
        """
        Initialize the ImageExpander instance with model loading if not already initialized.

        Example:
            >>> tools = ImageTools(...)
            >>> tools.init_expander_model()
        """
        self.init_expander()
        if not self.has_expander_model():
            self.expander.init_sr()
            self.expander.load_model()

    def get_model_scale(self) -> int:
        """
        Get the scale value of the loaded model.

        :return: The scale value of the loaded model.
        :rtype: int

        Example:
            >>> tools = ImageTools(...)
            >>> tools.init_expander_model()
            >>> tools.get_model_scale()
            2
        """
        result = 0
        self.init_expander()
        if self.has_expander():
            result = self.expander.model_conf.get_scale()
        return result

    def get_available_model_scales(self) -> list:
        """
        Get a list of available scale values for the model.

        :return: A list of available scale values.
        :rtype: list[int]

        Example:
            >>> tools = ImageTools(...)
            >>> tools.init_expander_model()
            >>> tools.get_available_model_scales()
            [2, 3, 4]
        """
        result = []
        self.init_expander()
        if self.has_expander():
            result = self.expander.model_conf.get_available_scales()
        return result

    def get_scale_selector(self) -> ScaleSelector:
        """
        Get the scale selection strategy.

        :return: The scale selection strategy.
        :rtype: ScaleSelector

        Example:
            >>> tools = ImageTools(...)
            >>> tools.get_scale_selector()
            ScaleSelector.AUTO_SCALE
        """
        self.init_expander()
        return self.expander.model_conf.scale_selector

    def is_auto_scale(self) -> bool:
        """
        Check if the current scale selection strategy is automatic.

        This method checks whether the current scale selection strategy being used by the
        ImageTools instance is automatic scale selection. An automatic scale selection strategy
        determines that the package will choose the appropriate upscale model scale based on the
        input image and output dimensions.

        :return: True if the scale selection strategy is automatic, False otherwise.
        :rtype: bool

        Example:
            >>> tools = ImageTools(...)
            >>> is_auto = tools.is_auto_scale()
            >>> print(is_auto)
            True
        """
        return self.get_scale_selector() == ScaleSelector.AUTO_SCALE

    def set_auto_scale(self) -> bool:
        """
        Set the image expander to automatically determine the best model scale for upscaling.

        :return: True if the auto scale selector was set successfully, False otherwise.
        :rtype: bool

        Example:
            >>> imgtools = ImageTools(...)
            >>> success = imgtools.set_auto_scale()
            >>> if success:
            >>>     print("Auto scale selector set successfully!")
            >>> else:
            >>>     print("Failed to set auto scale selector.")
        """
        self.init_expander()
        self.expander.model_conf.set_scale(2, set_default=False)
        self.expander.model_conf.set_scale_selector(ScaleSelector.AUTO_SCALE)
        return self.is_auto_scale()

    def set_fixed_scale(self, scale: int) -> bool:
        """
        Set a fixed upscale model scale for image processing.

        This method allows you to set a specific upscale model scale for image processing. The provided
        scale value must be a positive integer representing the upscale factor for the model.

        :param scale: The fixed upscale model scale.
        :type scale: int

        :return: True if the fixed scale was successfully set, False otherwise.
        :rtype: bool

        :raises ImgToolsException:
            If there is an issue setting the fixed scale.

        Example:
            >>> tools = ImageTools(...)
            >>> success = tools.set_fixed_scale(scale=2)
            >>> print(success)
            True
        """
        self.init_expander()
        if not self.expander.model_conf.set_scale(scale, set_default=False) \
                or not self.expander.model_conf.set_scale_selector(ScaleSelector.FIXED_SCALE):
            raise ImgToolsException(
                "Fatal Error: Unable to fix model scale to %s",
                scale
            )
        return True

    def has_conf(self) -> bool:
        """
        Check if the instance has a valid configuration.

        :return: True if the configuration is valid, False otherwise.
        :rtype: bool

        Example:
            >>> tools = ImageTools(...)
            >>> tools.has_conf()
            True
        """
        return isinstance(self.conf, ProcessConf) \
            and self.conf.is_ready()

    def set_source_path(self, source_path: str) -> bool:
        """
        Set the source_path property.

        :param source_path: The source path to set.
        :type source_path: str

        :return: True if the source path is set successfully, False otherwise.
        :rtype: bool

        Example:
            >>> tools = ImageTools(...)
            >>> tools.set_source_path("/path/to/source")
            True
        """
        return self.conf.set_source_path(source_path)

    def set_output_path(self, output_path: str) -> bool:
        """
        Set the output_path property.

        :param output_path: The output path to set.
        :type output_path: str

        :return: True if the output path is set successfully, False otherwise.
        :rtype: bool

        Example:
            >>> tools = ImageTools(...)
            >>> tools.set_output_path("/path/to/output")
            True
        """
        return self.conf.set_output_path(output_path)

    def set_output_formats(self, output_formats: list) -> bool:
        """
        Set the output_formats property.

        :param output_formats: List of dictionaries containing output format configurations.
        :type output_formats: list[dict]

        :return: True if the output formats are set successfully, False otherwise.
        :rtype: bool

        Example:
            >>> tools = ImageTools(...)
            >>> output_formats = [{"ext": ".jpg", "quality": 80}, {"ext": ".png", "compression": 5}]
            >>> result = tools.set_output_formats(output_formats)
            >>> print(result)
            True
        """
        return self.conf.set_output_formats(output_formats)

    def set_conf(self,
                 source_path: str,
                 output_path: str,
                 output_formats: list
                 ) -> bool:
        """
        Set the process configuration.

        :param source_path: The path to the source image or directory.
        :type source_path: str
        :param output_path: The path to the output directory.
        :type output_path: str
        :param output_formats: List of dictionaries containing output format configurations.
        :type output_formats: list[dict]

        :return: True if the configuration is set successfully, False otherwise.
        :rtype: bool

        Example:
            >>> tools = ImageTools(...)
            >>> source_path = "input.jpg"
            >>> output_path = "output"
            >>> output_formats = [{"ext": ".jpg", "quality": 80}, {"ext": ".png", "compression": 5}]
            >>> result = tools.set_conf(source_path, output_path, output_formats)
            >>> print(result)
            True
        """
        self.conf = ProcessConf(
            source_path=source_path,
            output_path=output_path,
            output_formats=output_formats
        )
        return self.conf.is_ready()

    def resize_image_if_needed(self,
                               image: ndarray,
                               output_format: dict
                               ) -> ndarray:
        """
        Resize the image if necessary based on the output format configuration.

        :param image: The input image as a NumPy ndarray.
        :type image: ndarray
        :param output_format: The output format configuration dictionary.
        :type output_format: dict

        :return: The resized image as a NumPy ndarray if resizing is needed.
        :rtype: ndarray

        Example:
            >>> tools = ImageTools(...)
            >>> input_image = ...  # Load your input image as a NumPy array
            >>> output_format = {"fixed_width": 800, "ext": ".jpg"}
            >>> resized_image = tools.resize_image_if_needed(input_image, output_format)
            >>> if resized_image is not None:
            >>>     print("Image resized.")
            >>> else:
            >>>     print("Image doesn't need resizing.")
        """
        if image is not None \
                and Ut.is_dict(output_format, not_null=True):
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
        else:
            return image
        return result

    def loop_on_upscale_stats(self,
                              upscale_stats: dict
                              ):
        """"""
        if Ut.is_dict(upscale_stats, not_null=True) \
                and Ut.is_list(upscale_stats.get('stats'), not_null=True):
            output_formats = self.conf.get_output_formats()
            nb_output_formats = len(self.conf.get_output_formats())
            for upscale in upscale_stats.get('stats'):
                key = upscale.get('key')
                output_format = None
                if 0 <= key < nb_output_formats:
                    output_format = output_formats[key]
                scale = upscale.get('scale')
                nb_upscale = upscale.get('nb_upscale')
                yield key, output_format, scale, nb_upscale

    def upscale_with_auto_scale(self,
                                image: ndarray,
                                upscale_stats: dict,
                                file_name: str
                                ) -> bool:
        """"""
        result = False
        if image is not None \
                and Ut.is_dict(upscale_stats, not_null=True) \
                and Ut.is_list(upscale_stats.get('stats'), not_null=True):
            self.init_expander_model()
            result = True
            for key, output_format, scale, nb_upscale in self.loop_on_upscale_stats(
                    upscale_stats=upscale_stats):
                if nb_upscale > 0:
                    logger.debug(
                        "[ImageTools] Image upscale with auto scale model-> %sx",
                        scale
                    )
                    start_upscale = time.perf_counter()
                    image = self.expander.many_image_upscale(
                        image=image,
                        nb_upscale=1,
                        scale=scale
                    )
                    logger.debug(
                        "[ImageTools] Upscale image with %sx model scale in %s s",
                        scale,
                        time.perf_counter() - start_upscale
                    )
                    resized = self.resize_image_if_needed(
                        image=image,
                        output_format=output_format
                    )
                else:
                    resized = self.resize_image_if_needed(
                        image=image,
                        output_format=output_format
                    )

                if key >= 0:
                    write_test = ImageTools.write_images_by_format(
                        image=resized,
                        output_path=self.conf.get_output_path(),
                        file_name=file_name,
                        output_formats=output_format.get('formats'))
                    if write_test is False:
                        result = False
        return result

    def upscale_with_fixed_scale(self,
                                 image: ndarray,
                                 upscale_stats: dict,
                                 file_name: str
                                 ) -> bool:
        """"""
        result = False
        if image is not None \
                and Ut.is_dict(upscale_stats, not_null=True) \
                and Ut.is_list(upscale_stats.get('stats'), not_null=True):
            self.init_expander_model()
            result = True
            upscale_counter = 0
            for key, output_format, scale, nb_upscale in self.loop_on_upscale_stats(
                    upscale_stats=upscale_stats):
                if nb_upscale > 0:
                    if nb_upscale > upscale_counter:
                        logger.debug(
                            "[ImageTools] Image upscale with fixed scale %s / %s -> %sx",
                            upscale_counter,
                            nb_upscale,
                            self.get_model_scale()
                        )
                        nb_upscale_needed = nb_upscale - upscale_counter
                        start_upscale = time.perf_counter()
                        image = self.expander.many_image_upscale(
                            image=image,
                            nb_upscale=nb_upscale_needed
                        )
                        logger.debug(
                            "[ImageTools] Upscale image with %sx model scale in %s s",
                            self.get_model_scale(),
                            time.perf_counter() - start_upscale
                        )
                        upscale_counter = nb_upscale
                    resized = self.resize_image_if_needed(
                        image=image,
                        output_format=output_format
                    )
                else:
                    resized = self.resize_image_if_needed(
                        image=image,
                        output_format=output_format
                    )

                if key >= 0:
                    write_test = ImageTools.write_images_by_format(
                        image=resized,
                        output_path=self.conf.get_output_path(),
                        file_name=file_name,
                        output_formats=output_format.get('formats'))
                    if write_test is False:
                        result = False
        return result

    def downscale_or_convert_images(self,
                                    image: ndarray,
                                    size: tuple,
                                    file_name: str
                                    ) -> ndarray or None:
        """
        Downscale or convert the image based on the output configuration and write images.

        :param image: The input image as a NumPy ndarray.
        :type image: ndarray
        :param size: The original image size as a tuple (width, height).
        :type size: tuple
        :param file_name: The base file name for the output images.
        :type file_name: str

        :return: True if the downscale or convert and write operations are successful, False otherwise.
        :rtype: bool

        Example:
            >>> tools = ImageTools(...)
            >>> input_image = ...  # Load your input image as a NumPy array
            >>> image_size = (1920, 1080)  # Example original image size
            >>> output_file_name = "output"
            >>> success = tools.downscale_or_convert_images(input_image, image_size, output_file_name)
            >>> if success:
            >>>     print("Images downscaled or converted and written successfully.")
            >>> else:
            >>>     print("Error occurred while processing images.")
        """
        result = False
        if image is not None \
                and Ut.is_tuple(size):
            resized = image
            result = True
            for output_format in self.conf.get_output_formats():
                resized = self.resize_image_if_needed(
                    image=resized,
                    output_format=output_format
                )
                if not ImageTools.write_images_by_format(
                        image=resized,
                        output_path=self.conf.get_output_path(),
                        file_name=file_name,
                        output_formats=output_format.get('formats')):
                    result = False
        return result

    def resize_image(self,
                     image: ndarray,
                     size: tuple,
                     upscale_stats: dict,
                     file_name: str
                     ) -> ndarray or None:
        """
        Resize the image based on the output configuration.

        :param image: The input image as a NumPy ndarray.
        :type image: ndarray
        :param size: The original image size as a tuple (width, height).
        :type size: tuple
        :param upscale_stats: Information about upscaling requirements.
        :type upscale_stats: dict
        :param file_name: The base file name for the output images.
        :type file_name: str

        :return: True if the image is resized and processed successfully, False otherwise.
        :rtype: bool

        Example:
            >>> tools = ImageTools(...)
            >>> input_image = ...  # Load your input image as a NumPy array
            >>> image_size = (1920, 1080)  # Example original image size
            >>> upscale_info = {'max_upscale': 2, 'stats': [{'key': 'webp', 'nb_upscale': 1}]}
            >>> output_file_name = "output"
            >>> success = tools.resize_image(input_image, image_size, upscale_info, output_file_name)
            >>> if success:
            >>>     print("Image resized and processed successfully.")
            >>> else:
            >>>     print("Error occurred while processing image.")
        """
        result = False
        if image is not None \
                and Ut.is_tuple(size) \
                and Ut.is_dict(upscale_stats, not_null=True)\
                and Ut.is_list(upscale_stats.get('stats'), not_null=True):
            # if upscale needed
            if upscale_stats.get('max_upscale') > 0:
                if self.is_auto_scale():
                    logger.debug(
                        "[ImageTools] Image need upscale x%s with auto scale",
                        upscale_stats.get('max_upscale')
                    )
                    upscale_stats = ModelScaleSelector.define_model_scale(
                        upscale_stats=upscale_stats,
                        available_scales=self.get_available_model_scales()
                    )
                    result = self.upscale_with_auto_scale(
                        image=image,
                        upscale_stats=upscale_stats,
                        file_name=file_name
                    )
                else:
                    logger.debug(
                        "[ImageTools] Image need upscale x%s with fixed scale (%sx)",
                        upscale_stats.get('max_upscale'),
                        self.get_model_scale()
                    )
                    result = self.upscale_with_fixed_scale(
                        image=image,
                        upscale_stats=upscale_stats,
                        file_name=file_name
                    )
            # if only downscale or convert image needed
            else:
                logger.debug(
                    "[ImageTools] Image need downscale or conversion."
                )
                result = self.downscale_or_convert_images(
                    image=image,
                    size=size,
                    file_name=file_name
                )
        return result

    def process_image(self,
                      source_path: str,
                      file_name: str
                      ) -> bool:
        """
        Process an image based on the provided source path and file name.

        :param source_path: The path to the source image file.
        :type source_path: str
        :param file_name: The base file name for the output images.
        :type file_name: str

        :return: True if the image is processed successfully, False otherwise.
        :rtype: bool

        Example:
            >>> tools = ImageTools(...)
            >>> source_path = "input.jpg"  # Example input image path
            >>> output_file_name = "output"
            >>> success = tools.process_image(source_path, output_file_name)
            >>> if success:
            >>>     print("Image processed successfully.")
            >>> else:
            >>>     print("Error occurred while processing image.")
        """
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
                upscale_stats = ModelScaleSelector.get_upscale_stats(
                    size=size,
                    output_formats=self.conf.get_output_formats(),
                    model_scale=self.get_model_scale()
                )

                result = self.resize_image(
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
        """
        Run the image processing operation, including upscale, downscale, and/or format conversion.

        This method initiates the image processing operation based on the configured settings.
        It handles both individual image files and all image files in a directory.

        :return: True if the image(s) processing completes successfully, False otherwise.
        :rtype: bool

        Example:
            >>> tools = ImageTools(...)
            >>> success = tools.run()
            >>> if success:
            >>>     print("Image processing completed successfully.")
            >>> else:
            >>>     print("Error occurred during image processing.")
        """
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
        """
        Calculate the dimensions for downscaling an image.

        :param size: The original image dimensions (height, width).
        :type size: tuple[int, int]
        :param fixed_height: The desired fixed height for downscaled image.
        :type fixed_height: int
        :param fixed_width: The desired fixed width for downscaled image.
        :type fixed_width: int

        :return: A dictionary containing dimensions for downscaling, either 'width' or 'height'.
        :rtype: dict[str, int] or None

        Example:
            >>> size = (800, 600)
            >>> fixed_height = 300
            >>> fixed_width = 400
            >>> ImageTools.get_downscale_size(size, fixed_height, fixed_width)
            >>> {'height': 300}

        Note:
            If both fixed_height and fixed_width are provided, the function calculates the most appropriate
            dimension to maintain the original aspect ratio.
        """
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
        """
        Read and load an image from the specified source path.

        :param source_path: The path to the image file.
        :type source_path: str

        :return: Loaded image as a NumPy ndarray or None if reading fails.
        :rtype: ndarray or None

        Example:
            >>> img = ImageTools.read_image("image.jpg")
            >>> type(img)
            >>> <class 'numpy.ndarray'>
        """
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
        """
        Set the output path and file name for the resized image.

        :param output_path: The path to the output directory.
        :type output_path: str
        :param file_name: The original file name of the image.
        :type file_name: str
        :param ext: The desired file extension for the resized image (e.g., '.jpg', '.png').
        :type ext: str
        :param size: The dimensions (height, width) of the resized image.
        :type size: tuple

        :return: The full path of the resized image file.
        :rtype: str or None

        Example:
            >>> output_path = "/path/to/output"
            >>> file_name = "image.jpg"
            >>> ext = ".png"
            >>> size = (800, 600)
            >>> result = ImageTools.set_write_path(output_path, file_name, ext, size)
            >>> print(result)
            >>> "/path/to/output/image_800x600.png"
        """
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
        """
        Get the options for writing images in JPEG format.

        :param output_format: The output format configuration dictionary.
        :type output_format: dict

        :return: A list of options for writing images in JPEG format, or None if no options are specified.
        :rtype: list or None

        Example:
            >>> output_format = {
            >>>     'quality': 90,
            >>>     'progressive': 1,
            >>>     'optimize': 1
            >>> }
            >>> result = ImageTools.get_jpeg_write_options(output_format)
            >>> print(result)
            >>> [cv2.IMWRITE_JPEG_QUALITY, 90, cv2.IMWRITE_JPEG_PROGRESSIVE, 1, cv2.IMWRITE_JPEG_OPTIMIZE, 1]
        """
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
        """
        Get the options for writing images in WebP format.

        :param output_format: The output format configuration dictionary.
        :type output_format: dict

        :return: A list of options for writing images in WebP format, or None if no options are specified.
        :rtype: list or None

        Example:
            >>> output_format = {
            >>>     'quality': 80
            >>> }
            >>> result = ImageTools.get_webp_write_options(output_format)
            >>> print(result)
            >>> [cv2.IMWRITE_WEBP_QUALITY, 80]
        """
        result = []
        if Ut.is_int(output_format.get('quality')):
            result.append(cv2.IMWRITE_WEBP_QUALITY)
            result.append(output_format.get('quality'))

        if not Ut.is_list(result, not_null=True):
            result = None
        return result

    @staticmethod
    def get_png_write_options(output_format: dict) -> list or None:
        """
        Get the options for writing images in PNG format.

        :param output_format: The output format configuration dictionary.
        :type output_format: dict

        :return: A list of options for writing images in PNG format, or None if no options are specified.
        :rtype: list or None

        Example:
            >>> output_format = {
            >>>     'compression': 3
            >>> }
            >>> result = ImageTools.get_png_write_options(output_format)
            >>> print(result)
            >>> [cv2.IMWRITE_PNG_COMPRESSION, 3]
        """
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
        """
        Write the image to the specified format.

        :param image: The image data as a NumPy ndarray.
        :type image: ndarray or None
        :param output_path: The path to the output directory.
        :type output_path: str
        :param file_name: The name of the output file.
        :type file_name: str
        :param output_format: The output format configuration dictionary.
        :type output_format: dict

        :return: True if the image is successfully written to the specified format, False otherwise.
        :rtype: bool

        Example:
            >>> output_format = {
            >>>     'ext': '.jpg',
            >>>     'quality': 90
            >>> }
            >>> result = ImageTools.write_image_format(image, 'output_dir', 'output_image', output_format)
            >>> print(result)
            >>> True
        """
        result = False
        if ProcessConf.is_valid_output_format(output_format):
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
                               output_formats: list
                               ) -> bool:
        """
        Write images to the specified formats.

        :param image: The image data as a NumPy ndarray.
        :type image: ndarray or None
        :param output_path: The path to the output directory.
        :type output_path: str
        :param file_name: The name of the output file.
        :type file_name: str
        :param output_formats: List of output format configuration dictionaries.
        :type output_formats: list

        :return: True if the images are successfully written to the specified formats, False otherwise.
        :rtype: bool

        Example:
            >>> image = ImageTools.read_image("input_image.jpg")
            >>> output_formats = [
            >>>     {'ext': '.jpg', 'quality': 90},
            >>>     {'ext': '.webp', 'quality': 80}
            >>> ]
            >>> result = ImageTools.write_images_by_format(image, 'output_dir', 'output_image', output_formats)
            >>> print(result)
            >>> True
        """
        result = False
        if Ut.is_list(output_formats, not_null=True):
            result = True
            for write_format in output_formats:
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
        """
        Write an image to the specified format.

        :param image: The image data as a NumPy ndarray.
        :type image: ndarray or None
        :param output_path: The path to the output directory.
        :type output_path: str
        :param file_name: The name of the output file.
        :type file_name: str
        :param ext: The extension of the output image file.
        :type ext: str
        :param options: List of image write options for the chosen format.
        :type options: list or None

        :return: True if the image is successfully written to the specified format, False otherwise.
        :rtype: bool

        Example:
            >>> image = ImageTools.read_image("input_image.jpg")
            >>> output_path = "output_dir"
            >>> file_name = "output_image"
            >>> ext = ".jpg"
            >>> options = [cv2.IMWRITE_JPEG_QUALITY, 90]
            >>> result = ImageTools.write_image(image, output_path, file_name, ext, options)
            >>> print(result)
            >>> True
        """
        result = False
        out_path = ImageTools.set_write_path(
            output_path=output_path,
            file_name=file_name,
            ext=ext,
            size=ImageToolsHelper.get_image_size(image)
        )
        can_write = image is not None \
            and out_path is not None
        if can_write:
            # Save the image
            if Ut.is_list(options, not_null=True):
                result = cv2.imwrite(out_path, image, options)
            else:
                result = cv2.imwrite(out_path, image)

            logger.info(
                "[ImageTools] Write image %s (size: %s)",
                out_path,
                ImageToolsHelper.get_string_file_size(
                    source_path=out_path
                )
            )
        if not can_write \
                or result is False:
            logger.warning(
                f"Unable to write image {file_name}."
            )
        return result

    @staticmethod
    def image_resize(image: ndarray,
                     width: int or float or None = None,
                     height: int or float or None = None,
                     inter=cv2.INTER_AREA
                     ) -> ndarray or None:
        """
        Resize an image.

        :param image: The image data as a NumPy ndarray.
        :type image: ndarray
        :param width: The desired width of the resized image.
        :type width: int or float or None, optional
        :param height: The desired height of the resized image.
        :type height: int or float or None, optional
        :param inter: The interpolation method used for resizing.
        :type inter: int, optional

        :return: The resized image as a NumPy ndarray.
        :rtype: ndarray or None

        :raises ImgToolsException: If unable to resize the image due to bad sizes.

        Example:
            >>> image = ImageTools.read_image("input_image.jpg")
            >>> resized_image = ImageTools.image_resize(image, width=800)
        """
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
