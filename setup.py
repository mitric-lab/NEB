#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Mon Jul  2 12:03:28 2018

@author: lindnerj
"""

from setuptools import setup, find_packages

def readme():
    with open('README.rst') as f:
        return f.read()

setup(name='metafalcon',
      version='0.0.1',
      scripts=['metafalcon/cltools/metaFALCON'],
      description='metadynamics package for the automatic localization of conical intersections',
      url='http://metafalcon.chemie.uni-wuerzburg.de/',
      author='Joachim Lindner',
      author_email='joachim.lindner@uni-wuerzburg.de',
      license='',
      packages=find_packages(),
      install_requires=[
          'numpy',
          'matplotlib',
          'argcomplete'
      ],
      classifiers=[
          'Programming Language :: Python :: 2.7',
          'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
          'Operating System :: OS Independent'
      ],
      include_package_data=True,
      use_2to3=True,
      zip_safe=False)
