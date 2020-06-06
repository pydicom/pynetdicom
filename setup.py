from setuptools import setup, find_packages
import os
import sys

# Version
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
VERSION_FILE = os.path.join(BASE_DIR, 'pynetdicom', '_version.py')
with open(VERSION_FILE) as fp:
    exec(fp.read())

with open("README.rst", "r") as fp:
    long_description = fp.read()

setup(
    name = "pynetdicom",
    packages = find_packages(),
    include_package_data = True,
    version = __version__,
    zip_safe = False,
    description = "A Python implementation of the DICOM networking protocol",
    long_description = long_description,
    long_description_content_type="text/x-rst",
    author = "",
    author_email = "scaramallion@users.noreply.github.com",
    url = "https://github.com/pydicom/pynetdicom",
    license = "MIT",
    keywords = (
        "dicom python medicalimaging radiotherapy oncology pydicom imaging"
    ),
    project_urls={
        'Documentation' : 'https://pydicom.github.io/pynetdicom/'
    },
    classifiers = [
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Science/Research",
        #"Development Status :: 4 - Beta",
        "Development Status :: 5 - Production/Stable",
        "Natural Language :: English",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Software Development :: Libraries",
    ],
    install_requires = ["pydicom>=1.4.2"],
)
