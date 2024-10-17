from setuptools import setup, find_packages

setup(
    name="dragon-runner",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'dragon-runner=dragon_runner.main:main',
        ],
    },
)

