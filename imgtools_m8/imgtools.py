import cv2
from cv2 import dnn_superres
from numpy import ndarray
import os
import pathlib
from ve_utils.utils import UType as Ut


class ImageExpander:

    def __init__(self,
                 model_conf: dict,
                 source_path: str,
                 output_conf: dict
                 ):
        self.model_conf = None

        self.source_path = source_path
        self.output_conf = None

        self.set_model_conf(model_conf)
        self.set_output_conf(output_conf)
        self.sr = None

    def is_ready(self) -> bool:
        """Test if is_ready"""
        return self.has_conf() \
            and self.sr is not None

    def has_conf(self) -> bool:
        """Test if instance has model_conf"""
        return self.has_model_conf() and self.has_model_conf()

    def has_model_conf(self) -> bool:
        """Test if instance has model_conf"""
        return self.is_model_conf(self.model_conf)

    def set_model_conf(self, model_conf: dict) -> bool:
        """Set model conf"""
        test = False
        if self.is_model_conf(model_conf):
            self.model_conf = model_conf
            if model_conf.get('path') is None:
                self.model_conf.update({
                    'path': os.path.join(os.path.abspath('..'), 'models')
                })
            test = True
        return test

    def has_output_conf(self) -> bool:
        """Test if instance has output_conf"""
        return self.is_output_conf(self.output_conf)

    def set_output_conf(self, output_conf: dict) -> bool:
        """Set output_conf"""
        test = False
        if self.is_output_conf(output_conf):
            self.output_conf = output_conf
            test = True
        return test

    def init_sr(self):
        """Init sr"""
        self.sr = dnn_superres.DnnSuperResImpl_create()

    def load_model(self):
        """Init sr"""
        test = False
        if self.has_model_conf():
            mod_path = os.path.join(
                self.model_conf.get('path'),
                self.model_conf.get('file_name')
            )
            if os.path.isfile(mod_path):
                self.sr.readModel(mod_path)
                # Set the desired model and scale to get correct pre- and post-processing
                self.sr.setModel(
                    self.model_conf.get('model_name'),
                    self.model_conf.get('scale')
                )
        return test

    def set_output_path(self, file_name: str, size: tuple):
        """Set image output path file"""
        path = None
        name, ext = self.cut_file_name(file_name)
        if Ut.is_str(name, not_null=True) \
                and Ut.is_tuple(size) \
                and len(size) == 2 \
                and Ut.is_str(ext, not_null=True):
            image_name = "%s_%s_%s%s" % (name, size[1], size[0], ext)
            path = os.path.join(self.output_conf.get('path'), image_name)
        return path

    def resize_need(self, image: ndarray):
        """Set image output path file"""
        result = None
        if type(image) == ndarray:
            (h, w) = self.get_image_size(image)
            fixed_height = self.output_conf.get('fixed_height')
            fixed_width = self.output_conf.get('fixed_width')
            fixed_size = self.output_conf.get('fixed_size')
            if Ut.is_int(fixed_width, not_null=True) \
                    and Ut.is_int(fixed_height, not_null=True) \
                    and (fixed_width < w
                         or fixed_height < h):
                if fixed_width >= fixed_height:
                    result = self.image_resize(
                        image=image,
                        height=fixed_height
                    )
                elif fixed_width <= fixed_height:
                    result = self.image_resize(
                        image=image,
                        width=fixed_width
                    )
            elif Ut.is_int(fixed_height, not_null=True) \
                    and fixed_height < h:
                result = self.image_resize(
                    image=image,
                    height=fixed_height
                )
            elif Ut.is_int(fixed_width, not_null=True) \
                    and fixed_width < w:
                result = self.image_resize(
                    image=image,
                    width=fixed_width
                )
            elif Ut.is_int(fixed_size, not_null=True) \
                    and (fixed_size < w
                         or fixed_size < h):
                if fixed_width >= fixed_height:
                    result = self.image_resize(
                        image=image,
                        height=fixed_height
                    )
                elif fixed_width <= fixed_height:
                    result = self.image_resize(
                        image=image,
                        width=fixed_width
                    )
            else:
                return image
        return result

    def need_upscale(self, image: ndarray):
        """Test if image need upscale"""
        result = False
        if type(image) == ndarray:
            (h, w) = self.get_image_size(image)
            fixed_height = self.output_conf.get('fixed_height')
            fixed_width = self.output_conf.get('fixed_width')
            fixed_size = self.output_conf.get('fixed_size')
            if Ut.is_int(fixed_width, not_null=True) \
                    and Ut.is_int(fixed_height, not_null=True) \
                    and fixed_width > w \
                    and fixed_height > h:
                result = True
            elif Ut.is_int(fixed_height, not_null=True) \
                    and fixed_height > h:
                result = True
            elif Ut.is_int(fixed_width, not_null=True) \
                    and fixed_width > w:
                result = True
            elif Ut.is_int(fixed_size, not_null=True) \
                    and fixed_size > w \
                    and fixed_size > h:
                result = True
        return result

    def loop_upscale_image(self, image: ndarray):
        """Set image output path file"""
        resized = None
        if self.need_upscale(image):
            max_loops = 10
            nb_loops = 0
            # Upscale the image one time
            resized = self.sr.upsample(image)
            if self.need_upscale(resized):

                while self.need_upscale(resized) or nb_loops > max_loops:
                    # Upscale the image
                    resized = self.sr.upsample(resized)
                    nb_loops += 1

            resized = self.resize_need(resized)
        else:
            resized = self.resize_need(image)

        return resized

    def upscale_image(self,
                     source_path: str,
                     output_path: str
                     ):
        """Expand an image file"""
        result = False
        if self.is_ready() \
                and os.path.isfile(source_path) \
                and Ut.is_str(output_path):
            image = cv2.imread(source_path)
            # Upscale the image
            resized = self.loop_upscale_image(image)

            out_path = self.set_output_path(
                file_name=output_path,
                size=self.get_image_size(resized)
            )
            if resized is not None and out_path is not None:
                # Save the image
                result = cv2.imwrite(out_path, resized)
            else:
                a = 2
        return result

    def run(self):
        """Run image enlarger"""
        result = False
        if self.has_conf():
            self.init_sr()
            self.load_model()
            if os.path.isfile(self.source_path):
                source_name = os.path.basename(self.source_path)
            elif os.path.isdir(self.source_path):
                files = self.get_images_list(self.source_path)
                if Ut.is_list(files, not_null=True):
                    for file in files:
                        if not self.upscale_image(
                                    source_path=os.path.join(self.source_path, file),
                                    output_path=file
                                ):
                            result = False
        return result

    @staticmethod
    def is_model_conf(model_conf: dict) -> bool:
        """Test if valid model conf"""
        return Ut.is_dict(model_conf) \
            and Ut.is_str(model_conf.get('file_name')) \
            and Ut.is_str(model_conf.get('model_name')) \
            and Ut.is_int(model_conf.get('scale'), mini=2, maxi=8)

    @staticmethod
    def is_output_conf(output_conf: dict) -> bool:
        """Test if valid model conf"""
        return Ut.is_dict(output_conf) \
            and os.path.isdir(output_conf.get('path')) \
            and Ut.is_str(output_conf.get('ext')) \
            and (Ut.is_int(output_conf.get('fixed_height'), not_null=True)
                 or Ut.is_int(output_conf.get('fixed_width'), not_null=True)
                 or Ut.is_int(output_conf.get('fixed_size'), not_null=True)
                 or Ut.is_int(output_conf.get('scale'), mini=2, maxi=20))

    @staticmethod
    def read_image(source_path: str):
        """Init sr"""
        img_src = None
        if os.path.isfile(source_path):
            img_src = cv2.imread(source_path)
        return img_src

    @staticmethod
    def get_image_size(image: ndarray):
        """Get image size (h, w)"""
        size = None
        if type(image) == ndarray:
            size = image.shape[:2]
        return size

    @staticmethod
    def image_resize(image: ndarray,
                     width: int | float | None = None,
                     height: int | float | None = None,
                     inter=cv2.INTER_AREA
                     ):
        """Resize an image"""
        # initialize the dimensions of the image to be resized and
        # grab the image size
        dim = None
        (h, w) = image.shape[:2]

        # if both the width and height are None, then return the
        # original image
        if width is None and height is None:
            return image

        # check to see if the width is None
        if width is None and height <= h:
            # calculate the ratio of the height and construct the
            # dimensions
            r = height / float(h)
            dim = (int(w * r), height)

        # otherwise, the height is None
        elif height is None and width <= w:
            # calculate the ratio of the width and construct the
            # dimensions
            r = width / float(w)
            dim = (width, int(h * r))

        else:
            pass
        resized = None
        if dim is not None:
            # resize the image
            resized = cv2.resize(image, dsize=dim, interpolation=inter)

        # return the resized image
        return resized

    @staticmethod
    def get_models_list(path):
        """List directory files"""
        return ImageExpander.get_files_list(path, ext='.pb')

    @staticmethod
    def get_images_list(path):
        """List directory files"""
        return ImageExpander.get_files_list(path, ext=ImageExpander.get_valid_images_ext())

    @staticmethod
    def get_files_list(path: str, ext: str | list | None = None):
        """List directory files"""
        return [
            f
            for f in os.listdir(path)
            if os.path.isfile(os.path.join(path, f))
            and (ext is None
                 or (Ut.is_list(ext, not_null=True) and ImageExpander.get_extension(f) in ext)
                 or (Ut.is_str(ext, not_null=True) and ImageExpander.get_extension(f) == ext)
                 )
        ]

    @staticmethod
    def get_valid_images_ext():
        """Get valid images extensions"""
        return ['.jpg', '.jpeg', '.png']

    @staticmethod
    def is_valid_image_ext(ext):
        """List directory files"""
        ext = ext.lower()
        return ext in ImageExpander.get_valid_images_ext()

    @staticmethod
    def cut_file_name(file_name: str, ext_len: int = 1) -> tuple:
        """Set image output path file"""
        name = None
        ext = ImageExpander.get_extension(file_name, ext_len)
        if Ut.is_str(file_name, not_null=True) \
                and Ut.is_str(ext):
            name = file_name.replace(ext, '')
        return name, ext

    @staticmethod
    def get_extension(path: str, ext_len: int = 1) -> str:
        """Set image output path file"""
        ext = None
        if Ut.is_str(path, not_null=True):
            ext_len = Ut.get_int(ext_len, default=1)
            if ext_len == 1:
                ext = pathlib.Path(path).suffix
            elif ext_len == 2:
                ext_list = pathlib.Path(path).suffixes[-2:]
                ext = "".join(ext_list)
            elif ext_len == 3:
                ext_list = pathlib.Path(path).suffixes[-3:]
                ext = "".join(ext_list)
            else:
                ext = "".join(pathlib.Path(path).suffixes)
        return ext
