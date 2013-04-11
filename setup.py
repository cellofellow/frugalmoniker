from distutils.core import setup

setup(
    name='frugalmoniker',
    version='0.0.0',
    author='Joshua D. Gardner',
    author_email='jgardner@izeni.com',
    py_modules=['frugalmoniker'],
    license='LICENSE',
    description='Library for NameCheap.com API',
    long_description=open('README.md').read(),
    install_requires=[
        'requests',
        'xmltodict',
    ],
)
