[![Python package](https://github.com/mano8/imgtools_m8/actions/workflows/python-package.yml/badge.svg)](https://github.com/mano8/imgtools_m8/actions/workflows/python-package.yml)
# imgtools_m8
Simple image tools package. Used to convert, downscale and/or upscale images.

Use deep learning and cv2 to upscale image using [Xavier Weber](https://github.com/Saafke) models, (more info [here](https://towardsdatascience.com/deep-learning-based-super-resolution-with-opencv-4fd736678066)).

## Installation

Install from GitHub repository :

To install directly from GitHub:

```plaintext
$ python3 -m pip install "git+https://github.com/mano8/imgtools_m8"
```

## How to use

This package automatically covert, downscale and/or upscale
an image file or a list of images from directory defined in source_path property.   
(See accepted extensions from [cv2 documentation](https://docs.opencv.org/4.8.0/d4/da8/group__imgcodecs.html#ga288b8b3da0892bd651fce07b3bbd3a56))

Example :   
```plaintext
    >>> # Set source as an image file 
    >>> source_path = /path/to/image.png
    >>> # Or set source as a directory containing your images
    >>> source_path = /path/to/directory
```   

Next you will need to define output configuration:
  - path: The output path
  - output_formats: The list of output formats,  
    who contains optional output sizes and output image format   
    (extension and compression options)

It is possible to resize images with different options:
 - fixed_width: resize image to exact width (in pixel)
 - fixed_height: resize image to exact height (in pixel)
 - fixed_size: resize image depending on first limitation reached (height or width)
 - fixed_width and fixed_height: resize image depending on first limitation reached.   
 same as fixed_size but can set different height/width values.  
   
Example :
The source file is 450px width and 280px height.
You want resized output file to exact width of 1600px and 800px.
And you need output formats as JPEG (with 80% quality) and WEBP (with 70% quality)
```plaintext
    >>> source_path = /path/to/image.png
    >>> output_conf = {
            # Output path
            'path': /my/output/path/directory, 
            'output_formats': [
                {  # Get resized output file to exact width of 1600px
                    'fixed_width': 1600,
                    'formats': [
                        # JPEg defauts are 'quality': 95, 'progressive': 0, 'optimize': 0
                        {'ext': '.jpg', 'quality': 80, 'progressive': 1, 'optimize': 1},
                        {'ext': '.webp', 'quality': 70},
                        {'ext': '.png', 'compression': 2}
                    ]
                },
                {  # Get resized output file to exact width of 800px
                    'fixed_width': 800,
                    'formats': [
                        {'ext': '.jpg', 'quality': 80},
                        {'ext': '.webp', 'quality': 70}
                    ]
                }
            ]

        }
        >>> imgtools = ImageTools(
            source_path=source_path,
            output_conf=output_conf
        )
        >>> imgtools.run()
```   
This will create 4 files in the output directory :
 - Two JPEG files resized as defined width (1600px and 800px), with 80% quality, JPEG progressive and optimize features enabled 
 - Two WEBP files resized as defined width (1600px and 800px), with 70% quality
 - One PNG file resized as defined width (1600px), with PNG compression level = 2 

The output file names are set as:
```plaintext
    >>> 'originalName'_'imageWidth'x'imageHeight'.'outputExtension'
    >>> # egg :
    >>> originalFileName_1400x1360.jpeg
```

In this case source file is precessed as:
 - upscale 2x (source file is now 900px/560px)
 - for 800px width output downscale and save as .jpeg an .webp
 - upscale 2x (source file is now 1800px/1120px)
 - for 1600px width output downscale and save as .jpeg an .webp

By default, the image tool use [EDSR_x2.pb](https://github.com/Saafke/EDSR_Tensorflow/tree/master)
deep learning model, to improve quality.

To load any compatible model of your choice to upscale the images,
you can define model_conf property.

The imgtools_m8 only contain EDSR (x2, x3, x4) and FSRCNN(x2, x3, x4) [models](https://github.com/mano8/imgtools_m8/tree/main/models).

If you want uses one of them set model_conf property as:

```plaintext
    >>> # Set EDSR_x4 model to upscale images
    >>> model_conf = {
        'file_name': 'EDSR_x4.pb',
    }
    >>> # Or set FSRCNN_x2 model to upscale images
    >>> model_conf = {
        'file_name': 'FSRCNN_x2.pb',
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
        'file_name': 'TF-ESPCN_x2.pb',
    }
```   

Here a complete example using TF-ESPCN_x2 model to upscale images :
```plaintext
    >>> # Set TF-ESPCN_x2 model to upscale images
    >>> model_conf = {
        'path': "/path/to/your/downloaded/model/directory",
        'file_name': 'TF-ESPCN_x2.pb',
    }
    >>> source_path = /path/to/image.png
    >>> output_conf = {
            # Output path
            'path': /my/output/path/directory, 
            'output_formats': [
                {  # Get resized output file to exact width of 1600px
                    'fixed_width': 1600,
                    'formats': [
                        {'ext': '.jpg', 'quality': 80},
                        {'ext': '.webp', 'quality': 70}
                    ]
                },
                {  # Get resized output file to exact width of 800px
                    'fixed_width': 800,
                    'formats': [
                        {'ext': '.jpg', 'quality': 80},
                        {'ext': '.webp', 'quality': 70}
                    ]
                }
            ]

        }
        >>> imgtools = ImageTools(
            source_path=source_path,
            output_conf=output_conf,
            model_conf=model_conf
        )
        >>> imgtools.run()
```   
