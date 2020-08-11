#!/usr/bin/env python3

import setuptools

# Hack to prevent stupid TypeError: 'NoneType' object is not callable error on
# exit of python setup.py test # in multiprocessing/util.py _exit_function when
# running python setup.py test (see
# http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html)
try:
    import multiprocessing
    assert multiprocessing
except ImportError:
    pass

setuptools.setup(
    name='orwell.shooter',
    version='0.0.2',
    description='Small program to shoot messages for tests.',
    author='',
    author_email='',
    packages=setuptools.find_packages(exclude="test"),
    test_suite='nose.collector',
    install_requires=['pyzmq', 'pyaml', 'cliff', 'simplejson', 'six',
                      'pyparsing', 'stevedore', 'pbr', 'protobuf'],
    tests_require=['nose', 'coverage'],
    entry_points={
        'console_scripts': [
            'thought_police = orwell.agent.main:main',
        ]
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX :: Linux',
        'Topic :: Utilities',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6'],
    python_requires='>=3.6.0',
)
