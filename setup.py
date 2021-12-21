from setuptools import setup, find_packages
from pathlib import Path


BASE_DIR = Path(__file__).parent

VERSION_FILE = BASE_DIR / "pynetdicom" / "_version.py"
with open(VERSION_FILE) as f:
    exec(f.read())

with open(BASE_DIR / "README.rst", "r") as f:
    long_description = f.read()

setup(
    name="pynetdicom",
    packages=find_packages(),
    include_package_data=True,
    version=__version__,
    zip_safe=False,
    description="A Python implementation of the DICOM networking protocol",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    author="",
    author_email="scaramallion@users.noreply.github.com",
    url="https://github.com/pydicom/pynetdicom",
    license="MIT",
    keywords=(
        "dicom network python medicalimaging radiotherapy oncology pydicom imaging"
    ),
    project_urls={"Documentation": "https://pydicom.github.io/pynetdicom/"},
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Science/Research",
        "Development Status :: 5 - Production/Stable",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Software Development :: Libraries",
    ],
    install_requires=["pydicom>=2.2.0"],
    extras_require={  # will also install from `install_requires`
        "apps": ["sqlalchemy"],
        "docs": [
            "sphinx",
            "sphinx_rtd_theme",
            "sphinx-copybutton",
            "sphinx-issues",
            "sphinxcontrib-napoleon",
            "numpydoc",
        ],
        "tests": ["pytest", "pyfakefs", "sqlalchemy"],
    },
    python_requires=">=3.7",
)
