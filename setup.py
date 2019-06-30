from setuptools import setup
import re
import sys
from subprocess import check_output


def readme():
    with open('README.rst') as f:
        return f.read()


def version():
    if sys.argv[1].startswith("bdist"):
        distname = check_output(["rpm --eval '%{dist}'"], shell=True).strip()
    else:
        distname = ""
    with open('netcontrold/__init__.py') as f:
        pattern = r"{}\W*=\W*'([^']+)'".format("__version__")
        vstr = re.findall(pattern, f.read())[0]
        return vstr + distname


setup(name='netcontrold',
      version=version(),
      description='Network control daemon for Open_vSwitch',
      long_description=readme(),
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Console',
          'License :: OSI Approved :: Apache Software License',
          'Programming Language :: Python :: 2.7',
          'Topic :: System :: Monitoring',
      ],
      url='https://gitlab.cee.redhat.com/gmuthukr/netcontrold-py',
      author='Gowrishankar Muthukrishnan',
      author_email='gmuthukr@redhat.com',
      license='Apache',
      packages=['netcontrold'],
      scripts=['ncd_ctl', 'ncd_watch', 'linux/ncd_cb_pktdrop'],
      data_files=[
          ('/usr/lib/systemd/system', ['rhel/netcontrold.service'])
      ],
      install_requires=['python'],
      include_package_data=True,
      zip_safe=False)
