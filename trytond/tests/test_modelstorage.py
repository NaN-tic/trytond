# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest

from trytond.error import UserError
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.tests.test_tryton import activate_module, with_transaction


class ModelStorageTestCase(unittest.TestCase):
    'Test ModelStorage'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_search_read_order(self):
        'Test search_read order'
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage')

        ModelStorage.create([{'name': i} for i in ['foo', 'bar', 'test']])

        rows = ModelStorage.search_read([])
        self.assertTrue(
            all(x['id'] < y['id'] for x, y in zip(rows, rows[1:])))

        rows = ModelStorage.search_read([], order=[('name', 'ASC')])
        self.assertTrue(
            all(x['name'] <= y['name'] for x, y in zip(rows, rows[1:])))

        rows = ModelStorage.search_read([], order=[('name', 'DESC')])
        self.assertTrue(
            all(x['name'] >= y['name'] for x, y in zip(rows, rows[1:])))

    @with_transaction()
    def test_search_count(self):
        "Test search_count"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage')
        ModelStorage.create([{'name': 'Test %s' % i} for i in range(10)])

        count = ModelStorage.search_count([])
        self.assertEqual(count, 10)

        count = ModelStorage.search_count([('name', '=', 'Test 5')])
        self.assertEqual(count, 1)

    @with_transaction()
    def test_browse_context(self):
        'Test context when browsing'
        pool = Pool()
        ModelStorageContext = pool.get('test.modelstorage.context')

        record, = ModelStorageContext.create([{}])
        record_context = {'_check_access': False}  # From Function.get

        self.assertDictEqual(record.context, record_context)

        # Clean the instance cache
        record = ModelStorageContext(record.id)

        with Transaction().set_context(foo='bar'):
            self.assertDictEqual(record.context, record_context)

            record = ModelStorageContext(record.id)
            self.assertDictContainsSubset({'foo': 'bar'}, record.context)

    @with_transaction()
    def test_save_mixed_context(self):
        'Test save with mixed context '
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage.required')

        foo = ModelStorage(name='foo')
        with Transaction().set_context(bar=True):
            bar = ModelStorage(name='bar')
        ModelStorage.save([foo, bar])
        self.assertNotEqual(foo._context, bar._context)

        foo.name = None
        with self.assertRaises(UserError):
            ModelStorage.save([foo, bar])
        self.assertIsNone(foo.name)
        self.assertEqual(bar.name, 'bar')

        Transaction().rollback()
        bar.name = None
        foo.name = 'foo'
        with self.assertRaises(UserError):
            ModelStorage.save([foo, bar])
        self.assertEqual(foo.name, 'foo')
        self.assertIsNone(bar.name)

    @with_transaction(context={'_check_access': True})
    def test_model_translations(self):
        'Test any user can translate fields and duplicate its records'
        pool = Pool()
        Transalatable = pool.get('test.char_translate')
        Lang = pool.get('ir.lang')
        User = pool.get('res.user')
        lang, = Lang.search([
                ('translatable', '=', False),
                ('code', '!=', 'en'),
                ], limit=1)
        lang.translatable = True
        lang.save()

        user = User(login='test')
        user.save()
        with Transaction().set_user(user.id):
            record = Transalatable(char='foo')
            record.save()
            with Transaction().set_context(lang=lang.code):
                record = Transalatable(record.id)
                record.char = 'bar'
                record.save()
                # Test we can copy and translations are copied
                copied_record, = Transalatable.copy([record])
                copied_record = Transalatable(copied_record.id)
                self.assertEqual(copied_record.char, 'bar')

    @with_transaction()
    def test_pyson_domain_same(self):
        "Test same pyson domain validation"
        pool = Pool()
        Model = pool.get('test.modelstorage.pyson_domain')

        Model.create([{'constraint': 'foo', 'value': 'foo'}] * 10)

        with self.assertRaises(UserError):
            Model.create([{'constraint': 'foo', 'value': 'bar'}] * 10)

    @with_transaction()
    def test_pyson_domain_unique(self):
        "Test unique pyson domain validation"
        pool = Pool()
        Model = pool.get('test.modelstorage.pyson_domain')

        Model.create(
            [{'constraint': str(i), 'value': str(i)} for i in range(10)])

        with self.assertRaises(UserError):
            Model.create(
                [{'constraint': str(i), 'value': str(i + 1)}
                    for i in range(10)])

    @with_transaction()
    def test_pyson_domain_single(self):
        "Test pyson domain validation for 1 record"
        pool = Pool()
        Model = pool.get('test.modelstorage.pyson_domain')

        Model.create([{'constraint': 'foo', 'value': 'foo'}])

        with self.assertRaises(UserError):
            Model.create([{'constraint': 'foo', 'value': 'bar'}])


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ModelStorageTestCase)
