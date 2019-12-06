# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

import versioneer

with open('README.md', 'r') as fp:
    readme = fp.read()

pkgs = find_packages('src')
print('found these packages:', pkgs)

schema_dir = 'data'

setup_args = {
    'name': 'buffalo-lab-data-to-nwb',
    'version': versioneer.get_version(),
    'cmdclass': versioneer.get_cmdclass(),
    'description': 'A package for converting Buffalo Lab data to the NWB standard',
    'long_description': readme,
    'long_description_content_type': 'text/markdown',
    'author': 'Luiz Tauffer, Maija Honig, Ryan Ly, Ben Dichter',
    'author_email': 'ben.dichter@gmail.com',
    'url': 'https://github.com/ben-dichter-consulting/buffalo-lab-data-to-nwb',
    'license': "BSD",
    'install_requires':
    [
        'pynwb', 'scipy', 'tqdm', 'natsort', 'colorama'
    ],
    'packages': pkgs,
    'package_dir': {'': 'src'},
    'classifiers': [
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "License :: OSI Approved :: BSD License",
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Operating System :: Unix",
        "Topic :: Scientific/Engineering :: Medical Science Apps."
    ],
    'keywords': 'python '
                'HDF '
                'HDF5 '
                'cross-platform '
                'open-data '
                'data-format '
                'open-source '
                'open-science '
                'reproducible-research '
                'neuroscience '
                'neurophysiology ',
    'zip_safe': False
}

if __name__ == '__main__':
    setup(**setup_args)
