# flask-whoosh

[![Build Status](https://travis-ci.org/drivet/flask-whoosh.svg?branch=master)](https://travis-ci.org/drivet/flask-whoosh)
[![Coverage Status](https://coveralls.io/repos/drivet/flask-whoosh/badge.svg)](https://coveralls.io/r/drivet/flask-whoosh)


Flask-Whoosh is a small Flask extension to make manipulating Whoosh
indexes a bit more convenient in the context of a Flask web application.

Features:

* ability to create indexes without having to pre-create the parent folder
* manages a pool of reusable Whoosh search objects
* provides easy access to a Whoosh AsyncWriter, allowing web applications to 
simply modify the index and commit without worrying about other requests
interfering.

## Usage

```
from flask import Flask
from flask_whoosh import Whoosh
from whoosh.fields import TEXT

app = Flask(__name__)
app.config.from_pyfile('config.py')
fw = Whoosh(app)
```

Later on:

```
from whoosh.query.qcore import Every
with app.app_context():
    results = fw.searcher.search(Every())    
```

## Tests

Install the packages listed in requirements-test.txt, and then run

```
nosetests --with-coverage --cover-package=flask_whoosh
```

Or if you want nice reporting:

```
nosetests --with-spec --spec-color --with-coverage --cover-package=flask_whoosh
```