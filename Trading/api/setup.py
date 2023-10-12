import os.path
import setuptools

path_requirements = os.path.dirname(os.path.abspath(__file__)) + "/requirements.txt"

setuptools.setup(
    name="fastapi-backend",
    version="0.0.0",
    description="Backend template for fastapi-based applications",
    packages=setuptools.find_packages(),
    python_requires=">=3.10",
    install_requires=open(path_requirements).read().splitlines(),
    extras_require={
        'dev': ['freezegun', 'pytest', 'black'],
    }
)
