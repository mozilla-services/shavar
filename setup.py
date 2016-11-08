import os
from setuptools import setup, find_packages

from pip.req import parse_requirements
from pip.download import PipSession

from shavar import __version__

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.txt')) as f:
    CHANGES = f.read()
install_reqs = parse_requirements('requirements.txt', session=PipSession())
requires = [str(ir.req) for ir in install_reqs]

setup(name='shavar',
      version=__version__,
      description='shavar',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
          "Programming Language :: Python",
          "Framework :: Pyramid",
          "Topic :: Internet :: WWW/HTTP",
          "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
      ],
      author='Luke Crouch',
      author_email='lcrouch@mozilla.com',
      url='',
      keywords='web pyramid pylons',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=requires,
      test_suite="shavar",
      entry_points="""\
      [paste.app_factory]
      main = shavar:main
      """,
      )
