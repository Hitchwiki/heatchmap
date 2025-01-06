from setuptools import setup, find_packages

setup(
    name="heatchmap",
    version="0.1.0",
    author="Hitchwiki",
    author_email="info@hitchwiki.org",
    description="A package for estimation and visualization of hitchhiking quality.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Hitchwiki/heatchmap",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    install_requires=[
        "geopandas",
        "ipykernel",
        "ipython",
        "matplotlib",
        "numpy",
        "osmnx",
        "pandas",
        "scikit-learn",
        "scipy",
        "shapely",
        "tqdm",
    ],
)
