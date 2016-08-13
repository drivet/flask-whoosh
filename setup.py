"""
Flask-Whoosh
-------------

Small Flask extension to make manipulating Whoosh indexes a slightly more
convenient in the context of a Flask web application.
"""
from setuptools import setup


setup(
    name='Flask-Whoosh',
    version='0.1.0',
    url='https://github.com/drivet/flask-whoosh.git',
    license='MIT',
    author='Desmond Rivet',
    author_email='desmond.rivet@gmail.com',
    description='Flask extension to manipulate Whoosh indexes',
    long_description=__doc__,
    py_modules=['flask_whoosh'],
    # if you would be using a package instead use packages instead
    # of py_modules:
    # packages=['flask_sqlite3'],
    zip_safe=False,
    platforms='any',
    install_requires=[
        'Flask',
        'whoosh'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: Flask',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    keywords='flask whoosh search indexing'
)
