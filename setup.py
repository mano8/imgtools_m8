import pathlib
from setuptools import setup

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

setup(
    name='imgtools_m8',
    version='1.0.0',
    packages=['tests', 'imgtools_m8'],
    package_dir={
        'imgtools_m8': 'imgtools_m8',
        'tests': 'tests'
    },
    package_data={
        'imgtools_m8': ['models/*.pb'],
        'tests': ['sources_test/*.jpg', 'sources_test/*.txt', 'output_test/']
    },
    url='https://github.com/mano8/imgtools_m8',
    license='Apache',
    author='Eli Serra',
    author_email='eli.serra173@gmail.com',
    description='Simple image tools package. Used to convert, downscale or upscale images.',
    long_description=README,
    long_description_content_type="text/markdown",
    classifiers=[
            "License :: OSI Approved :: Apache Software License",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.5",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
      ],
    include_package_data=True,
    install_requires=[
          'opencv-contrib-python>=4.7.0.72',
          've_utils>=2.5.3',
          'numpy>=1.25.0'
      ],
    extras_require={
              "TEST": [
                    "pytest>=7.1.2",
                    "coverage"
              ]
      },
    python_requires='>3.5.2',
    zip_safe=False
)
