import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="p2fa",
    version="0.0.1",
    author="papagandalf",
    author_email="papagandalf@gmail.com",
    description="Python wrapper for Penn Forced Aligner",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/papagandalf/p2fa_py3",
    packages=setuptools.find_packages(),
    package_data={'p2fa': ['model/*/*']},
    scripts=['bin/p2fa'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
