from setuptools import setup, find_packages
import os
import sys

# Version
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
VERSION_FILE = os.path.join(BASE_DIR, 'pynetdicom3', '_version.py')
with open(VERSION_FILE) as fp:
    exec(fp.read())

setup(
    name = "pynetdicom3",
    packages = find_packages(),
    include_package_data = True,
    version = __version__,
    zip_safe = False,
    description = "A Python 3 implementation of the DICOM networking protocol",
    author = "",
    author_email = "",
    url = "https://github.com/pydicom/pynetdicom3",
    license = "LICENCE.txt",
    keywords = "dicom python medicalimaging",
    classifiers = [
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Science/Research",
        "Development Status :: 2 - Pre-Alpha",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Software Development :: Libraries",
    ],
    install_requires = [
        "pydicom"
    ]
)
