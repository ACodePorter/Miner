import os
import ast

from setuptools import find_packages, setup


def read_file(file: str):
    with open(file, 'rt', encoding='utf-8') as f:
        return f.read()


exec(read_file(os.path.join(os.path.dirname(
    __file__), 'russell1000miner', '_version.py')))

setup(
    name='russell1000miner',
    version=version,
    description='Russell 1000 Miner',
    # author='',
    # author_email='',
    license='Apache License v2',
    # url=''
    packages=find_packages(),
    install_requires=read_file('requirements.txt'),
    zip_safe=False,
    test_suite='test'
    # include_package_data=True,
    # package_data={}
)
