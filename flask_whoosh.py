"""Small Flask extension to make manipulating Whoosh indexes a slightly more
convenient in the context of a Flask web application.
"""

import os
import queue as Queue

from flask import current_app
from whoosh.index import create_in, open_dir, exists_in
from whoosh.fields import Schema
from whoosh.writing import AsyncWriter

# Find the stack on which we want to store the database connection.
# Starting with Flask 0.9, the _app_ctx_stack is the correct one,
# before that we need to use the _request_ctx_stack.
try:
    from flask import _app_ctx_stack as stack
except ImportError:
    from flask import _request_ctx_stack as stack


class DirectoryAlreadyExists(Exception):
    """This exception is raised when we try to create an index over an existing
    one without the right option.
    """
    def __init__(self, folder):
        super(DirectoryAlreadyExists, self).__init__()
        self.folder = folder

    def __str__(self):
        return repr(self.folder)


class Whoosh(object):
    """This class integrates a Whoosh index into one or more Flask
    applications.

    The basic API consists of a searcher and a writer property.  The searcher
    comes from a pool of searcher objects and is returned upon completion of
    the request.  The writer is just an AsyncWriter.
    """
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Set this extension up for this application"""
        app.config.setdefault('WHOOSH_INDEX_ROOT', '/tmp')
        app.config.setdefault('WHOOSH_INDEX_NAME', '')
        app.config.setdefault('WHOOSH_SEARCHER_MAX', 10)
        if hasattr(app, 'teardown_appcontext'):
            app.teardown_appcontext(Whoosh.teardown)
        else:
            app.teardown_request(Whoosh.teardown)

    @staticmethod
    def init_index(fields, clear=False):
        return WhooshManager.init_index(current_app.config['WHOOSH_INDEX_ROOT'],
                                        current_app.config['WHOOSH_INDEX_NAME'],
                                        fields, clear)

    def _setup_whoosh(self):
        """Set up the infrastructure required to manipulate whoosh indexes"""
        if not hasattr(current_app, 'whoosh'):
            searcher_max = current_app.config['WHOOSH_SEARCHER_MAX']
            current_app.whoosh = WhooshManager(searcher_max,
                                               Whoosh._open_index())

    @staticmethod
    def _open_index():
        """Open configured whoosh index"""
        index_root = current_app.config['WHOOSH_INDEX_ROOT']
        name = current_app.config['WHOOSH_INDEX_NAME'] or None
        return open_dir(index_root, indexname=name)

    @property
    def searcher(self):
        """Property for a whoosh searcher, used to perform queries"""
        self._setup_whoosh()
        ctx = stack.top
        if ctx is not None:
            if not hasattr(ctx, 'whoosh_searcher'):
                ctx.whoosh_searcher = current_app.whoosh.get_searcher()
            return ctx.whoosh_searcher

    @property
    def writer(self):
        """Property for a whoosh AsyncWriter, used to write to the index"""
        self._setup_whoosh()
        ctx = stack.top
        if ctx is not None:
            if not hasattr(ctx, 'whoosh_writer'):
                ctx.whoosh_writer = current_app.whoosh.writer()
            return ctx.whoosh_writer

    @staticmethod
    def teardown(exception):
        """Call this when we want to clean up after a request"""
        ctx = stack.top
        if hasattr(ctx, 'whoosh_searcher'):
            current_app.whoosh.put_searcher(ctx.whoosh_searcher)


class WhooshManager(object):
    """Manages Whoosh specific state, like the index object and the searcher pool.

    Whoosh searchers are kept in a pool, which is managed here in a thread safe
    manner.  In addition, this class provide a way to create a thread safe
    writer as well.
    """
    def __init__(self, search_max, index):
        self.search_max = search_max
        self.index = index
        self.search_pool = self._initialize_searcher_pool()

    @staticmethod
    def init_index(index_root, name, fields, clear=False):
        """Initialize and return a Whoosh index.

        If WHOOSH_INDEX_ROOT exists and isn't a folder, or it's a folder but it
        isn't empty and it isn't an Whoosh index, throw a DirectoryAlreadyExists
        exception.

        If WHOOSH_INDEX_ROOT doesn't exist, or it exists and is empty, then go
        ahead and create the index.

        If WHOOSH_INDEX_ROOT already contains a Whoosh index, then throw a
        DirectoryAlreadyExists exception if clear is False, otherwise clear the
        index and create a new one.
        """
        name = name or None

        if os.path.exists(index_root) and not os.path.isdir(index_root):
            # index root exists and is not a directory
            raise DirectoryAlreadyExists(index_root)

        if os.path.isdir(index_root) \
           and not exists_in(index_root, indexname=name) \
           and os.listdir(index_root):
            # index root is a directory and is non-empty and non-index
            raise DirectoryAlreadyExists(index_root)

        if os.path.isdir(index_root) and \
           exists_in(index_root, indexname=name) \
           and not clear:
            # index root is an existing index and we don't have permission
            # to clear it
            raise DirectoryAlreadyExists(index_root)

        # either the directory doesn't exist, or it does but it's empty, or
        # it does, and has an index, but we have permission to clear it.

        if not os.path.exists(index_root):
            os.makedirs(index_root)

        schema = Schema(**fields)
        return create_in(index_root, schema=schema, indexname=name)

    def _initialize_searcher_pool(self):
        """Basically what the method says.  We create the searcher queue
        and fill it with wrappers around Whoosh searcher objects.  We create
        the searcher object lazily when someone obtains a wrapper and it has no
        searcher initialized.
        """
        queue = Queue.LifoQueue(self.search_max)
        for i in range(self.search_max):
            queue.put({'searcher': None})
        return queue

    def writer(self):
        return AsyncWriter(self.index)

    def get_searcher(self):
        """Fetch a searcher object from the pool"""
        wrapper = self.search_pool.get()
        if wrapper['searcher'] is None:
            wrapper['searcher'] = self.index.searcher()
        wrapper['searcher'] = wrapper['searcher'].refresh()
        return wrapper['searcher']

    def put_searcher(self, searcher):
        """Return a search object to the pool"""
        self.search_pool.put({'searcher': searcher})

