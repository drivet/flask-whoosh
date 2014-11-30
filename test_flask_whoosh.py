import unittest
from flask_whoosh import Whoosh, DirectoryAlreadyExists
from whoosh.index import create_in
from whoosh.qparser import QueryParser
from whoosh.fields import Schema
from flask import Flask
from whoosh.fields import TEXT, ID
import os
import shutil
import tempfile
from flask import _app_ctx_stack as stack

class TestFlaskWhooshDefaultConfiguration(unittest.TestCase):
    def test_has_default_min_searcher(self):
        app = Flask(__name__)
        whoosh  = Whoosh()
        whoosh.init_app(app)
        self.assertEquals(1, app.config['WHOOSH_SEARCHER_MIN'])

    def test_has_default_max_searcher(self):
        app = Flask(__name__)
        whoosh  = Whoosh()
        whoosh.init_app(app)
        self.assertEquals(10, app.config['WHOOSH_SEARCHER_MAX'])
        

class TestFlaskWhooshIndexCreation(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.whoosh  = Whoosh()
        self.whoosh.init_app(self.app)
        self.app.config['WHOOSH_INDEX_ROOT'] = '/tmp/toodles'

    def test_index_created_when_directory_does_not_exist(self):
        self.assertFalse(os.path.exists(self.app.config['WHOOSH_INDEX_ROOT']))
        with self.app.app_context():
            self.whoosh.init_index({'content': TEXT})
            self.assertTrue(os.path.exists(self.app.config['WHOOSH_INDEX_ROOT']))

    def test_index_created_when_empty_directory_exists(self):
        os.makedirs('/tmp/toodles')
        with self.app.app_context():
            self.whoosh.init_index({'content': TEXT})
            self.assertTrue(os.path.exists(self.app.config['WHOOSH_INDEX_ROOT']))

    def test_index_not_created_when_full_directory_exists(self):
        os.makedirs('/tmp/toodles')
        with open('/tmp/toodles/stuff.txt', 'w') as f:
            f.write('blah')
        with self.app.app_context():
            self.assertRaises(DirectoryAlreadyExists, self.whoosh.init_index,{'content': TEXT})
 
    def test_index_not_created_when_file_exists_at_path(self):
        with open('/tmp/toodles', 'w') as f:
            f.write('blah')
        with self.app.app_context():
            self.assertRaises(DirectoryAlreadyExists, self.whoosh.init_index,{'content': TEXT})

    def tearDown(self):
        if os.path.isdir('/tmp/toodles'):
            shutil.rmtree('/tmp/toodles')
        elif os.path.isfile('/tmp/toodles'):
            os.remove('/tmp/toodles') 


class TestFlaskWhooshSearcher(unittest.TestCase):
    def setUp(self):
        self.root_dir = tempfile.mkdtemp()
        schema = Schema(path = ID(stored=True), content = TEXT)
        self.index = create_in(self.root_dir, schema = schema)
        writer = self.index.writer()
        writer.add_document(path=u'/blah/hello', content=u'this is awesome content')
        writer.commit()

        self.app = Flask(__name__)
        self.whoosh  = Whoosh()
        self.whoosh.init_app(self.app)
        self.app.config['WHOOSH_INDEX_ROOT'] =  self.root_dir

    def test_searcher_is_usable(self): 
        with self.app.app_context():
            qp = QueryParser("content", schema=self.index.schema)
            q = qp.parse(u"awesome")
            with self.whoosh.searcher as searcher:
                results = searcher.search(q)
                self.assertEquals(1, len(results))
                self.assertEquals('/blah/hello', results[0]['path'])

    def test_searcher_is_taken_from_and_returned_to_pool(self):
        with self.app.app_context():
            with self.whoosh.searcher as searcher:
                ctx = stack.top
                whoosh_manager = self.app.extensions['whoosh']
                self.assertEquals(9, whoosh_manager.search_pool.qsize())
                self.assertIsNotNone(ctx.whoosh_search_accessor)
        self.assertEquals(10, whoosh_manager.search_pool.qsize())

    def test_same_searcher_returned_in_multiple_calls(self):
        with self.app.app_context():
            searcher1 = self.whoosh.searcher
            searcher2 = self.whoosh.searcher
            self.assertEquals(searcher1, searcher2)

    def tearDown(self):
        assert self.root_dir != '/tmp/' and self.root_dir.startswith('/tmp/')
        shutil.rmtree(self.root_dir)


class TestFlaskWhooshWriter(unittest.TestCase):
    def setUp(self):
        self.root_dir = tempfile.mkdtemp()
        schema = Schema(path = ID(stored=True), content = TEXT)
        self.index = create_in(self.root_dir, schema = schema)

        self.app = Flask(__name__)
        self.whoosh = Whoosh()
        self.whoosh.init_app(self.app)
        self.app.config['WHOOSH_INDEX_ROOT'] =  self.root_dir

    def test_writer_is_usable(self):
        with self.app.app_context():
            writer = self.whoosh.writer
            writer.add_document(path=u'/blah/hello', content=u'this is awesome content')
            writer.commit()
            qp = QueryParser("content", schema=self.index.schema)
            q = qp.parse(u"awesome")
            with self.index.searcher() as s:
                results = s.search(q)
                self.assertEquals(1, len(results))
                self.assertEquals('/blah/hello', results[0]['path'])

    def test_same_writer_returned_in_multiple_calls(self):
        with self.app.app_context():
            writer1 = self.whoosh.writer
            writer2 = self.whoosh.writer
            self.assertEquals(writer1, writer2)
            
    def tearDown(self):
        assert self.root_dir != '/tmp/' and self.root_dir.startswith('/tmp/')
        shutil.rmtree(self.root_dir)
