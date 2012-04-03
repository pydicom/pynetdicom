#!/usr/bin/env python
from distribute_setup import use_setuptools
use_setuptools()

from setuptools import setup, find_packages
import os
import os.path

import sys

setup(name="pynetdicom",
      packages = find_packages(),
      include_package_data = True,
      version="0.5",
      zip_safe = False, # want users to be able to see included examples,tests
      description="Pure python implementation of the DICOM network stack",
      author="Patrice Munger",
      author_email="patricemunger@gmail.com",
      url="http://pynetdicom.googlecode.com",
      license = "MIT license",
      keywords = "dicom python medical imaging",
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
      long_description = """
      pynetdicom is a pure python package implementing the DICOM
      network protocol.  Working with pydicom, it allows DICOM clients
      (SCUs) and servers (SCPs) to be easily created.  DICOM is a
      standard (http://medical.nema.org) for communicating medical
      images and related information such as reports and radiotherapy
      objects.
      
      The main class is ApplicationEntity. User typically create an
      ApplicationEntity object, specifying the SOP service class
      supported as SCP and SCU, and a port to listen to. The user then
      starts the ApplicationEntity which runs in a thread. The use can
      initiate associations as SCU or respond to remove SCU
      association with the means of callbacks.

      See the `Getting Started <http://code.google.com/p/pynetdicom/wiki/GettingStarted>`_ 
      wiki page for installation and basic information, and the 
      `Pynetdicom User Guide <http://code.google.com/p/pynetdicom/wiki/PynetdicomUserGuide>`_ page 
      for an overview of how to use the pynetdicom library.
      """,
      test_loader = "dicom.test.run_tests:MyTestLoader",
      test_suite = "dummy_string"
     )
