from setuptools import setup
import os
import sys

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(name='netcontrold-py',
    version='0.1',
    description='Network control daemon for Open_vSwitch',
    url='https://gitlab.cee.redhat.com/gmuthukr/netcontrold-py',
    author='Gowrishankar Muthukrishnan',
    author_email='gmuthukr@redhat.com',
    license='Apache',
    packages=['app', 'lib',],
    long_description=read('README.rst'),
    include_package_data=True,
    zip_safe=False)
