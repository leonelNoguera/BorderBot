from distutils.core import setup
from Cython.Build import cythonize

setup(
    ext_modules = cythonize(['client.py', 'borderbot.py', 'db.py', 'strategy.py', 'server.py'])
)
