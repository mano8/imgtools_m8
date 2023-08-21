[![Python package](https://github.com/mano8/imgtools_m8/actions/workflows/python-package.yml/badge.svg)](https://github.com/mano8/imgtools_m8/actions/workflows/python-package.yml)
[![PyPI package](https://img.shields.io/pypi/v/imgtools_m8.svg)](https://pypi.org/project/imgtools_m8/)
[![codecov](https://codecov.io/gh/mano8/imgtools_m8/branch/main/graph/badge.svg?token=0J31F62GB7)](https://codecov.io/gh/mano8/imgtools_m8)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/c401bed6812d4f9bb77bfaee16cf0abe)](https://www.codacy.com/gh/mano8/imgtools_m8/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=mano8/imgtools_m8&amp;utm_campaign=Badge_Grade)
[![Downloads](https://static.pepy.tech/badge/imgtools-m8)](https://pepy.tech/project/imgtools-m8)
# imgtools_m8
Simple image tools package. Used to convert, downscale and/or upscale images.

Use deep learning and cv2 to upscale image using [Xavier Weber](https://github.com/Saafke) models, (more info [here](https://towardsdatascience.com/deep-learning-based-super-resolution-with-opencv-4fd736678066)).

## Installation

Install from GitHub repository :

To install directly from GitHub:

```plaintext
$ python3 -m pip install "git+https://github.com/mano8/imgtools_m8 --upgrade"
```

To install from PypI :

``python3 -m pip install imgtools_m8 --upgrade``

## How to use

This package automatically covert, downscale and/or upscale
an image file or a list of images from directory defined in source_path property,
to output_path directory.   
See [examples](https://github.com/mano8/imgtools_m8/tree/main/examples) for more use case.
(See accepted extensions from [cv2 documentation](https://docs.opencv.org/4.8.0/d4/da8/group__imgcodecs.html#ga288b8b3da0892bd651fce07b3bbd3a56))

It is possible to resize images with different options:
 - fixed_width: resize image to exact width (in pixel)
 - fixed_height: resize image to exact height (in pixel)
 - fixed_size: resize image depending on first limitation reached (height or width)
 - fixed_width and fixed_height: resize image depending on first limitation reached.   
 same as fixed_size but can set different height/width values.  
   
Example :  
The source file is 340px width and 216px height.
<div align="center">
  <img src="https://raw.githubusercontent.com/mano8/imgtools_m8/main/tests/sources_test/recien_llegado.jpg" alt="Recien Llegado @Cezar llañez" width="340" height="216" />   
  <p>Recien llegado by <a href="https://www.ichingmaestrodelosespiritus.com/">@Cezar yañez</a></p>
</div>

We want resized output file to exact width of 1900px and 1200px.
And we need output formats as JPEG (with 80% quality) and WEBP (with 70% quality)
```plaintext
    >>> output_formats = [
                {  # Get resized output file to exact width of 1600px
                    'fixed_width': 1900,
                    'formats': [
                        # JPEg defauts are 'quality': 95, 'progressive': 0, 'optimize': 0
                        {'ext': '.jpg', 'quality': 80, 'progressive': 1, 'optimize': 1},
                    ]
                },
                {  # Get resized output file to exact width of 800px
                    'fixed_width': 1200,
                    'formats': [
                        {'ext': '.jpg', 'quality': 80},
                        {'ext': '.webp', 'quality': 70}
                        {'ext': '.png', 'compression': 2}
                    ]
                }
            ]
        >>> imgtools = ImageTools(
            source_path="./tests/dummy_dir/recien_llegado.jpg",
            output_path="/my/output/path/directory",
            output_formats=output_formats
        )
        >>> imgtools.run()
```   
This will create 4 files in the output directory :
 - Two JPEG files resized as defined width (1900px and 1200px), with 80% quality, JPEG progressive and optimize features enabled 
 - Two WEBP files resized as defined width (1900px and 1200px), with 70% quality
 - One PNG file resized as defined width (1900px), with PNG compression level = 2 

The output file names are set as:
```plaintext
    >>> 'originalName'_'imageWidth'x'imageHeight'.'outputExtension'
    >>> # egg :
    >>> originalFileName_1400x1360.jpeg
```
One of above results is :
<div align="center">
  <img src="https://raw.githubusercontent.com/mano8/imgtools_m8/main/tests/output_test/recien_llegado_1200x762.jpg" alt="Recien Llegado @Cezar llañez" width="1200px" />
  <p>recien_llegado_1200x762.jpg by <a href="https://www.ichingmaestrodelosespiritus.com/">@Cezar yañez</a></p>
</div>

In this case source file is precessed as:
 - upscale 2x (source file is now 680px/432px)
 - upscale 2x (source file is now 1360px/864px)
 - for 1200px width output downscale and save as 
   recien_llegado_1200x762.jpg
   recien_llegado_1200x762.webp
   recien_llegado_1200x762.png
 - upscale 2x (source file is now 2720px/1728px)
 - for 1900px width output downscale and save as recien_llegado_1900x1207.jpeg an .webp

By default, the image tool use [EDSR_x2.pb](https://github.com/Saafke/EDSR_Tensorflow/tree/master)
deep learning model, to improve quality.

To load any compatible model of your choice to upscale the images,
you can define model_conf property.

The imgtools_m8 only contain EDSR (x2, x3, x4) [models](https://github.com/mano8/imgtools_m8/tree/main/imgtools_m8/models).

If you want uses one of them set model_conf property as:

```plaintext
    >>> # Set EDSR_x4 model to upscale images
    >>> model_conf = {
        'model_name': 'edsr',
        'scale': 4,
    }
    >>> # Or set FSRCNN_x2 model to upscale images
    >>> model_conf = {
        'model_name': 'edsr',
        'scale': 2,
    }
```   

In case you want uses 
[another compatible model](https://github.com/opencv/opencv_contrib/tree/master/modules/dnn_superres), 
you may download the desired ``.pb`` file,
and set model_conf property as:

```plaintext
    >>> # Set TF-ESPCN_x2 model to upscale images
    >>> model_conf = {
        'path': "/path/to/your/downloaded/model/directory",
        'model_name': 'espcn',
        'scale': 2,
    }
```   

Here a complete example using TF-ESPCN_x2 model to upscale images :
```plaintext
    >>> # Set TF-ESPCN_x2 model to upscale images
    >>> model_conf = {
        'path': "/path/to/your/downloaded/model/directory",
        'model_name': 'espcn',
        'scale': 2,
    }
    >>> output_formats = [
                {  # Get resized output file to exact width of 1600px
                    'fixed_width': 1900,
                    'formats': [
                        # JPEg defauts are 'quality': 95, 'progressive': 0, 'optimize': 0
                        {'ext': '.jpg', 'quality': 80, 'progressive': 1, 'optimize': 1},
                    ]
                },
                {  # Get resized output file to exact width of 800px
                    'fixed_width': 1200,
                    'formats': [
                        {'ext': '.jpg', 'quality': 80},
                        {'ext': '.webp', 'quality': 70}
                        {'ext': '.png', 'compression': 2}
                    ]
                }
            ]
        >>> imgtools = ImageTools(
            source_path="./tests/dummy_dir/recien_llegado.jpg",
            output_path="/my/output/path/directory",
            output_formats=output_formats,
            model_conf=model_conf
        )
        >>> imgtools.run()
```   
