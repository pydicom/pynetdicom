from setuptools import setup, find_packages
import os
import sys

setup(name="pynetdicom3",
      packages = find_packages(),
      include_package_data = True,
      version='0.1.0',
      zip_safe = False,
      description="A Python 3 implementation of the DICOM networking protocol",
      author="",
      author_email="",
      url="",
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
      install_requires=[#"pydicom >= 1.0.0"
                       ]
     )
