from distutils.core import setup
from Cython.Build import cythonize

setup(
    ext_modules = cythonize(['borderbot_real_time.py', 'borderbot.py', 'client.py', 'db_client.py', 'db.py', 'server.py', 'strategy.py'])
)
