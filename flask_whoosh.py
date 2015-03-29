"""Flask extension to manipulate Whoosh indexes"""
from __future__ import absolute_import

import os
import Queue

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
    """This is raised when we try to create an index over an existing one
    without the right option
    """
    def __init__(self, folder):
        super(DirectoryAlreadyExists, self).__init__()
        self.folder = folder

    def __str__(self):
        return repr(self.folder)


class Whoosh(object):
    """This class integrates a Whoosh index into one or more Flask
    applications
    """
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Set this extension up for this application"""
        app.config.setdefault('WHOOSH_INDEX_ROOT', '/tmp')
        app.config.setdefault('WHOOSH_INDEX_NAME', '')
        app.config.setdefault('WHOOSH_SEARCHER_MIN', 1)
        app.config.setdefault('WHOOSH_SEARCHER_MAX', 10)
        if hasattr(app, 'teardown_appcontext'):
            app.teardown_appcontext(self.teardown)
        else:
            app.teardown_request(self.teardown)

    def init_index(self, fields, clear=False):
        """Initialize an index.  If clear is True we will delete the existing
        index if there is one"""

        index_root = current_app.config['WHOOSH_INDEX_ROOT']
        name = current_app.config['WHOOSH_INDEX_NAME'] or None

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

    def setup_whoosh(self):
        """Set up the infrastructure required to manipulate whoosh indexes"""
        if not hasattr(current_app, 'extensions'):
            current_app.extensions = {}
        if 'whoosh' not in current_app.extensions:
            manager = WhooshManager(current_app.config, self.open_index())
            current_app.extensions['whoosh'] = manager

    def open_index(self):
        """Open an existing whoosh index"""
        index_root = current_app.config['WHOOSH_INDEX_ROOT']
        name = current_app.config['WHOOSH_INDEX_NAME'] or None
        return open_dir(index_root, indexname = name)

    @property
    def searcher(self):
        """Property for a whoosh searcher, used to perform queries"""
        self.setup_whoosh()
        ctx = stack.top
        if ctx is not None:
            if not hasattr(ctx, 'whoosh_search_accessor'):
                whoosh_manager = current_app.extensions['whoosh']
                ctx.whoosh_search_accessor = whoosh_manager.search_pool.get()
            searcher = ctx.whoosh_search_accessor.searcher
            return searcher

    @property
    def writer(self):
        """Property for a whoosh write, used to write to the index"""
        self.setup_whoosh()
        ctx = stack.top
        if ctx is not None:
            if not hasattr(ctx, 'whoosh_writer'):
                whoosh_manager = current_app.extensions['whoosh']
                ctx.whoosh_writer = AsyncWriter(whoosh_manager.index)
            return ctx.whoosh_writer

    def teardown(self, exception):
        """Call this when we want to clean up after a request"""
        ctx = stack.top
        if hasattr(ctx, 'whoosh_search_accessor'):
            whoosh_manager = current_app.extensions['whoosh']
            whoosh_manager.search_pool.put(ctx.whoosh_search_accessor)


class WhooshManager(object):
    """
    The application level stuff for whoosh.
    """
    def __init__(self, config, index):
        self.minimum = config['WHOOSH_SEARCHER_MIN']
        self.maximum = config['WHOOSH_SEARCHER_MAX']
        self.index = index
        self.search_pool = self.initialize_searcher_queue()

    def initialize_searcher_queue(self):
        """Basically what the method says.  We create the searcher queue
        and fill it with
        """
        queue = Queue.LifoQueue(self.maximum)
        for i in range(self.minimum):
            queue.put(SearchAccessor(self.index))
        for i in range(self.maximum - self.minimum):
            queue.put(SearchAccessor(self.index, init=True))
        return queue


class SearchAccessor(object):
    """Lazy search wrapper.  Will create a whoosh search on demand"""
    def __init__(self, index, init=False):
        self.index = index
        self._searcher = None
        if init:
            self._searcher = self.index.searcher()

    @property
    def searcher(self):
        """Searcher property.  Creates and then caches a whoosh searcher"""
        if self._searcher is None:
            self._searcher = self.index.searcher()
        self._searcher = self._searcher.refresh()
        return self._searcher
