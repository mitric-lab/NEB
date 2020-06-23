"""Installer for geodesic interpolation package.
Install the package into python environment, and provide an entry point for the
main interpolation script.

To run the package as standalone
"""
from setuptools import setup
 


setup(
  name='NEB',
  version='0.0.1',
  description='A small library of path optimization scripts',
  packages=packages,
  entry_points = {
    'console_scripts': [
      'optimize_neb=NEB.__main__:main'
    ],
  },
)
