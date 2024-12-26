import sys

from setuptools import setup, find_packages

import gpudog


extra_description = {}
try:
    with open('README.md', mode='r') as doc:
        extra_description['long_description'] = doc.read()
        extra_description['long_description_content_type'] = 'text/markdown'
except OSError:
    pass

setup(
    name='',
    version=gpudog.__version__,
    description=gpudog.__doc__,
    **extra_description,
    license=gpudog.__license__,
    author=gpudog.__author__,
    author_email=gpudog.__email__,
    url="https://github.com/lsrami/gpu_dog",
    packages=find_packages(include=['gpudog', 'gpudog.*']),
    entry_points={
        'console_scripts': [
            'gpudog=gpudog.main:main',
            'gpu-dog=gpudog.main:main'
        ]
    },
    install_requires=(['windows-curses'] if sys.platform == 'windows' else []) + [
        'pynvml',
        'blessed',
        'apscheduler',
        'requests',
        'argparse'
    ],
    python_requires='>=3.5, <4',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Environment :: GPU',
        'Environment :: Console',
        'Environment :: Console :: Curses',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: System Administrators',
        'Topic :: System :: Hardware',
        'Topic :: System :: Monitoring',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities',
    ],
    keywords='nvidia, nvidia-smi, GPU, wechat, htop',
    project_urls={
        'Bug Reports': 'https://github.com/lsrami/gpu_dog/issues',
        'Source': 'https://github.com/lsrami/gpu_dog',
    },
)
