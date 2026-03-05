from setuptools import setup, find_packages

setup(
    name="pyimouapi",
    version="1.2.3",
    packages=find_packages(),
    install_requires=[
        "aiohttp>=3.11.9,<4.0",
        "async-timeout>=4.0",
        "simpleeval>=1.0.3",
    ],
    description="A package for imou open api",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Imou-OpenPlatform/Py-Imou-Open-Api",
    author="Imou-OpenPlatform",
    author_email="cloud_openteam_service@imou.com",
    license="MIT",
    classifiers=[
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries",
    ],
)
