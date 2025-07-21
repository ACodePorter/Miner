import os

from setuptools import find_packages, setup


def read_file(file: str):
    with open(file, 'rt', encoding='utf-8') as f:
        return f.read()


exec(read_file(os.path.join(os.path.dirname(
    __file__), 'maintainer', '_version.py')))

setup(
    name='maintainer',
    version=__version__,
    description='Maintainer for Miner',
    # author='',
    # author_email='',
    license='Apache License v2',
    # url=''
    packages=find_packages(),
    install_requires=read_file('requirements.txt'),
    zip_safe=False,
    test_suite='test'
)
