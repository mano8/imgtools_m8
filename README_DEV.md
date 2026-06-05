# imgtools_m8 dev

## Included utilities

### Exif to json

Extract and format all exif data to json

### Exif remover

Remove all exif data from images

### Scan dir

Scan dir and subdirs to get tree of all valid images. Can classify images by:

- portrait/paysage
- format
- size

### Image classifier

Classify images with image reconizion tool.

### Normalise image size and/or image conversion

| Option | Type | Description |
| ------ | ------ | ------ |
| `source_path` | str | Source path of directory or single image. |
| `include_subdirs` | Optional(bool) | If True apply to all images included subdirs, by default limited to 4. |
| `output_path` | str | Output path directory. |
| `flatten_output` | Optional(bool) | If True and `include_subdirs` is True, output all images in same directory, and images names will start with tree dir names as `dir1_dir2_image_name.jpeg`. |
| `output_formats` | str | Output path directory. |

The package provides versatile options to resize and or covert images, including:

| Option | Type | Description |
| ------ | ------ | ------ |
| `fixed_width` | Optional(int) | Resizing images to an exact width in pixels. |
| `fixed_height` | Optional(int) | Resizing images to an exact height in pixels. |
| `fixed_size` | Optional(int) | Resizing images based on the highest limitation reached (height or width). |
| `allow_upscale` | Optional(bool) | If True and where the original image size exceeds the specified output dimensions, the package automatically applies upscaling using pre-trained models. |
| `max_byte_size` | Optional(int) | Allow to fix max byte size of output images. |
| `formats` | Optional(list) | Allow to define differents output formats types for images eg `jpeg, webp, avif...` with related formats options. |

> - It's possible to combine `fixed_width` and `fixed_height`: Resizing images based on the highest limitation reached, while allowing different height and width values.  
> - `fixed_size` can't be combined with `fixed_width` or `fixed_height`.
> - If `fixed_width`/`fixed_height`/`fixed_size` not set, output images without change size and upsacling is disabled.
> - If `formats` is not set, output image format using default Pillow options
> - You need to set `fixed_width`/`fixed_height`/`fixed_size` and/or `formats`.

#### Accepted Output Formats

| Format | Description |
| ------ | ------ |
| `jpeg` | Select `jpeg` image output. |
| `webp` | Select `webp` image output. |
| `png` | Select `png` image output. |
| `gif` | Select `gif` image output. |
| `avif` | Select `avif` image output. |

> If `max_byte_size` is set, and image output byte size is upper than this value, will change above value to allow byte size at most equal to `max_byte_size` value.

- **`jpeg` format options**:

    | Option | Type | Description |
    | ------ | ------ | ------ |
    | `name` | str | Set as `jpeg`. |
    | `quality` | Optional(int) | Define `jpeg` quality (1-100). |
    | `optimize` | Optional(bool) | Enable Huffman table optimization. |
    | `progressive` | Optional(bool) | Use progressive JPEG encoding. |
    | `subsampling` | Optional(Union[int, str]) | Chroma subsampling: `0`, `1`, `2` or `4:4:4`, `4:2:2`, `4:2:0`. Controls color resolution. |

- **`webp` format options**:

    | Option | Type | Description |
    | ------ | ------ | ------ |
    | `name` | str | Set as `webp`. |
    | `quality` | Optional(int) | Define quality (1-100). |
    | `lossless` | Optional(bool) | Use lossless compression. |
    | `method` | Optional(int) | Define Compression method (0-6). |

- **`png` format options**:

    | Option | Type | Description |
    | ------ | ------ | ------ |
    | `name` | str | Set as `png`. |
    | `optimize` | Optional(bool) | Enable PNG optimization. |
    | `compression_level` | Optional(int) | PNG compression level (0-9). |
    | `interlace` | Optional(bool) | Enable PNG interlacing. |

- **`gif` format options**:

    | Option | Type | Description |
    | ------ | ------ | ------ |
    | `name` | str | Set as `gif`. |
    | `optimize` | Optional(bool) | Enable GIF optimization. |

- **`avif` format options**:

    | Option | Type | Description |
    | ------ | ------ | ------ |
    | `name` | str | Set as `gif`. |
    | `quality` | Optional(int) | AVIF quality (1-100). |
    | `lossless` | Optional(bool) | Use lossless AVIF compression. |
