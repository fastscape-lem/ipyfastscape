#!/usr/bin/env python

"""The setup script."""

from os.path import exists

from setuptools import find_packages, setup

with open('requirements.txt') as f:
    install_requires = f.read().strip().split('\n')

if exists('README.md'):
    with open('README.md') as f:
        long_description = f.read()
else:
    long_description = ''

CLASSIFIERS = [
    'Development Status :: 3 - Alpha',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent',
    'Intended Audience :: Science/Research',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Topic :: Scientific/Engineering',
]

setup(
    name='ipyfastscape',
    description='Interactive widgets for topographic data analysis and modelling in Jupyter notebooks.',
    long_description=long_description,
    python_requires='>=3.6',
    maintainer='Benoit Bovy',
    maintainer_email='benbovy@gmail.com',
    classifiers=CLASSIFIERS,
    url='https://github.com/fastscape-lem/ipyfastscape',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    include_package_data=True,
    install_requires=install_requires,
    license='MIT',
    zip_safe=False,
    keywords=['fastscape', 'jupyter', 'xarray', 'topography', 'landscape'],
    use_scm_version={'version_scheme': 'post-release', 'local_scheme': 'dirty-tag'},
    setup_requires=['setuptools_scm', 'setuptools>=30.3.0'],
)
