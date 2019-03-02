# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import time
import unittest

from trytond import cache as cache_mod
from trytond.cache import freeze, MemoryCache
from trytond.tests.test_tryton import with_transaction, activate_module
from trytond.tests.test_tryton import DB_NAME, USER
from trytond.transaction import Transaction


cache = MemoryCache('test.cache')


class CacheTestCase(unittest.TestCase):
    "Test Cache"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def setUp(self):
        super().setUp()
        clear_timeout = cache_mod._clear_timeout
        cache_mod._clear_timeout = 1
        self.addCleanup(
            setattr, cache_mod, '_clear_timeout', clear_timeout)

    def tearDown(self):
        MemoryCache.drop(DB_NAME)

    def testFreeze(self):
        "Test freeze"
        self.assertEqual(freeze([1, 2, 3]), (1, 2, 3))
        self.assertEqual(freeze({
                    'list': [1, 2, 3],
                    }),
            frozenset([('list', (1, 2, 3))]))
        self.assertEqual(freeze({
                    'dict': {
                        'inner dict': {
                            'list': [1, 2, 3],
                            'string': 'test',
                            },
                        }
                    }),
            frozenset([('dict',
                        frozenset([('inner dict',
                                    frozenset([
                                            ('list', (1, 2, 3)),
                                            ('string', 'test'),
                                            ]))]))]))

    @with_transaction()
    def test_memory_cache_set_get(self):
        "Test MemoryCache set/get"
        cache.set('foo', 'bar')

        self.assertEqual(cache.get('foo'), 'bar')

    @with_transaction()
    def test_memory_cache_drop(self):
        "Test MemoryCache drop"
        cache.set('foo', 'bar')
        MemoryCache.drop(DB_NAME)

        self.assertEqual(cache.get('foo'), None)

    def test_memory_cache_transactions(self):
        "Test MemoryCache with concurrent transactions"
        transaction1 = Transaction().start(DB_NAME, USER)
        self.addCleanup(transaction1.stop)

        cache.set('foo', 'bar')
        self.assertEqual(cache.get('foo'), 'bar')

        transaction2 = transaction1.new_transaction()
        self.addCleanup(transaction2.stop)

        cache.clear()
        self.assertEqual(cache.get('foo'), None)

        cache.set('foo', 'baz')
        self.assertEqual(cache.get('foo'), 'baz')

        Transaction().set_current_transaction(transaction1)
        self.addCleanup(transaction1.stop)
        self.assertEqual(cache.get('foo'), 'bar')

        transaction2.commit()
        self.assertEqual(cache.get('foo'), None)

    def test_memory_cache_sync(self):
        "Test MemoryCache synchronisation"
        with Transaction().start(DB_NAME, USER):
            cache.clear()
        time.sleep(cache_mod._clear_timeout)
        last = cache._clean_last

        with Transaction().start(DB_NAME, USER):
            self.assertGreater(cache._clean_last, last)

    def test_memory_cache_old_transaction(self):
        "Test old transaction does not fill cache"
        transaction1 = Transaction().start(DB_NAME, USER)
        self.addCleanup(transaction1.stop)

        # Clear cache from new transaction
        transaction2 = transaction1.new_transaction()
        self.addCleanup(transaction2.stop)
        cache.clear()
        transaction2.commit()

        # Set value from old transaction
        Transaction().set_current_transaction(transaction1)
        self.addCleanup(transaction1.stop)
        cache.set('foo', 'baz')

        # New transaction has still empty cache
        transaction3 = transaction1.new_transaction()
        self.addCleanup(transaction3.stop)
        self.assertEqual(cache.get('foo'), None)


def suite():
    func = unittest.TestLoader().loadTestsFromTestCase
    suite = unittest.TestSuite()
    for testcase in (CacheTestCase,):
        suite.addTests(func(testcase))
    return suite
