from pathlib import Path

import setuptools

VERSION = "0.1.12"

NAME = "heatchmap"

INSTALL_REQUIRES = [
    "datasets==3.2.0",
    "huggingface-hub==0.27.1",
    "geopandas==1.0.1",
    "matplotlib==3.10.0",
    "numpy==2.2.1",
    "osmnx==1.7.0",
    "pandas==2.2.3",
    "rasterio==1.4.3",
    "scikit-learn==1.6.0",
    "scipy==1.15.0",
    "shapely==2.0.6",
    "tqdm==4.67.1",
]


setuptools.setup(
    name=NAME,
    version=VERSION,
    description="A package for estimation and visualization of hitchhiking quality.",
    url="https://github.com/Hitchwiki/heatchmap",
    project_urls={
        "Source Code": "https://github.com/Hitchwiki/heatchmap",
    },
    author="Hitchwiki",
    author_email="info@hitchwiki.org",
    license="MIT",
    classifiers=[
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    # Requirements
    install_requires=INSTALL_REQUIRES,
    packages=setuptools.find_packages(),
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
)