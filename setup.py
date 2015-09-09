#!/usr/bin/env python
from distribute_setup import use_setuptools
use_setuptools()

from setuptools import setup, find_packages
import os
import os.path

import sys

__version__ = open('netdicom/__version__.py').read().split('"')[1]
print __version__

setup(name="pynetdicom",
      packages = find_packages(),
      include_package_data = True,
      version=__version__,
      zip_safe = False, # want users to be able to see included examples,tests
      description="Pure python implementation of the DICOM network protocol",
      author="Patrice Munger",
      author_email="patricemunger@gmail.com",
      url="http://pynetdicom.googlecode.com",
      license = "LICENCE.txt",
      keywords = "dicom python medicalimaging",
      classifiers = [
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Science/Research",
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Software Development :: Libraries",
        ],
      long_description = open('README.txt').read(),
      install_requires=["pydicom >= 0.9.7"]
     )
