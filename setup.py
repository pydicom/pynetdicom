from setuptools import setup, find_packages
import os
import sys

setup(name="pynetdicom",
      packages = find_packages(),
      include_package_data = True,
      version=['0', '9', '0'],
      zip_safe = False,
      description="Implementation of the DICOM network protocol",
      author="Patrice Munger",
      author_email="patricemunger@gmail.com",
      url="",
      license = "LICENCE.txt",
      keywords = "dicom python medicalimaging",
      classifiers = [
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Science/Research",
        "Development Status :: 2 - Pre-Alpha",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Software Development :: Libraries",
        ],
      long_description = open('README.txt').read(),
      install_requires=["pydicom >= 1.0.0"]
     )
