import os.path

import setuptools

path_requirements = os.path.dirname(os.path.abspath(__file__)) + "/requirements.txt"
setuptools.setup(
    name="Trading",
    version="1.0.0",
    description="Trading",
    packages=setuptools.find_packages(),
    python_requires=">=3.6",
    install_requires=open(path_requirements).read().splitlines(),
)

