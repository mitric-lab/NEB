#!/usr/bin/env python
# -*- coding: utf-8 -*-


from setuptools import setup, find_packages

def readme():
    with open('README.rst') as f:
        return f.read()

setup(name='NEB',
      version='0.0.3',
      scripts=['NEB/optimize_neb'],
      description='optimize a reaction path using the nudged elastic band algorithm',
      url='https://github.com/hochej/NEB',
      author='Joscha Hoche',
      author_email='joscha.hoche@uni-wuerzburg.de',
      license='',
      packages=find_packages(),
      install_requires=[
          'numpy',
          'argparse',
          'future'
      ],
      classifiers=[
          'Programming Language :: Python :: 3.7',
          'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
          'Operating System :: OS Independent'
      ],
      include_package_data=True,
      use_2to3=True,
      zip_safe=False)
