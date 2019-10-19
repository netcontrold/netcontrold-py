from setuptools import setup
import re
import sys
import platform
from subprocess import check_output


def readme():
    with open('README.rst') as f:
        return f.read()


def version():
    distname = ""
    if sys.argv[1].startswith("bdist"):
        distro = platform.dist()[0]
        if distro in ['redhat']:
            distname = check_output(
                ["rpm --eval '%{dist}'"], shell=True).strip().decode()

    with open('netcontrold/__init__.py') as f:
        pattern = r"{}\W*=\W*'([^']+)'".format("__version__")
        vstr = re.findall(pattern, f.read())[0]
        return vstr + distname


setup(name='netcontrold',
      version=version(),
      description='Network control daemon for Open_vSwitch ',
      long_description=readme(),
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'License :: OSI Approved :: Apache Software License',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 3',
          'Topic :: System :: Monitoring',
      ],
      url='https://github.com/netcontrold/netcontrold-py.git',
      author='Gowrishankar Muthukrishnan',
      author_email='gmuthukr@redhat.com',
      license='Apache',
      packages=['netcontrold'],
      scripts=['ncd_ctl', 'ncd_watch', 'linux/ncd_cb_pktdrop'],
      data_files=[
          ('/usr/lib/systemd/system', ['rhel/netcontrold.service'])
      ],
      python_requires='>=3',
      setup_requires=["wheel"],
      include_package_data=True,
      zip_safe=False)
