#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import time
from trytond.osv import fields, OSV
from string import Template


class SequenceType(OSV):
    "Sequence type"
    _name = 'ir.sequence.type'
    _description = __doc__
    name = fields.Char('Sequence Name', required=True, translate=True)
    code = fields.Char('Sequence Code', required=True)

SequenceType()


class Sequence(OSV):
    "Sequence"
    _name = 'ir.sequence'
    _description = __doc__
    name = fields.Char('Sequence Name', required=True, translate=True)
    code = fields.Selection('code_get', 'Sequence Type', required=True)
    active = fields.Boolean('Active')
    prefix = fields.Char('Prefix')
    suffix = fields.Char('Suffix')
    number_next = fields.Integer('Next Number')
    number_increment = fields.Integer('Increment Number')
    padding = fields.Integer('Number padding')

    def __init__(self):
        super(Sequence, self).__init__()
        self._constraints += [
            ('check_prefix_suffix', 'invalid_prefix_suffix'),
        ]
        self._error_messages.update({
            'missing': 'Missing sequence!',
            'invalid_prefix_suffix': 'Invalid prefix/suffix!',
            })

    def default_active(self, cursor, user, context=None):
        return 1

    def default_number_increment(self, cursor, user, context=None):
        return 1

    def default_number_next(self, cursor, user, context=None):
        return 1

    def default_padding(self, cursor, user, context=None):
        return 0

    def code_get(self, cursor, user, context=None):
        sequence_type_obj = self.pool.get('ir.sequence.type')
        sequence_type_ids = sequence_type_obj.search(cursor, user, [],
                context=context)
        sequence_types = sequence_type_obj.browse(cursor, user,
                sequence_type_ids, context=context)
        return [(x.code, x.name) for x in sequence_types]

    def check_prefix_suffix(self, cursor, user, ids):
        "Check prefix and suffix"

        for sequence in self.browse(cursor, user, ids):
            try:
                self._process(cursor, user, sequence.prefix)
                self._process(cursor, user, sequence.suffix)
            except:
                return False
        return True

    def _process(self, cursor, user, string, date=None, context=None):
        date_obj = self.pool.get('ir.date')
        if not date:
            date = date_obj.today(cursor, user, context=context)
        year = date.strftime('%Y')
        month = date.strftime('%m')
        day = date.strftime('%d')
        return Template(string or '').substitute(
                year=year,
                month=month,
                day=day,
                )

    def get_id(self, cursor, user, domain, context=None):
        '''
        Return sequence value for the domain

        :param cursor: the database cursor
        :param user: the user id
        :param domain: a domain or a sequence id
        :param context: the context
        :return: the sequence value
        '''
        if context is None:
            context = {}
        if isinstance(domain, (int, long)):
            domain = [('id', '=', domain)]

        sequence_ids = self.search(cursor, user, domain, limit=1,
                context=context)
        date = context.get('date')
        if sequence_ids:
            sequence = self.browse(cursor, user, sequence_ids[0],
                    context=context)
            self.write(cursor, user, sequence.id, {
                'number_next': sequence.number_next + sequence.number_increment,
                }, context=context)
            if sequence.number_next:
                return self._process(cursor, user, sequence.prefix, date=date,
                        context=context) + \
                        '%%0%sd' % sequence.padding % sequence.number_next + \
                        self._process(cursor, user, sequence.suffix, date=date,
                                context=context)
            else:
                return self._process(cursor, user, sequence.prefix, date=date,
                        context=context) + \
                        self._process(cursor, user, sequence.suffix, date=date,
                                context=context)
        self.raise_user_error(cursor, 'missing', context=context)

    def get(self, cursor, user, code, context=None):
        return self.get_id(cursor, user, [('code', '=', code)], context=context)

Sequence()


class SequenceStrict(Sequence):
    "Sequence Strict"
    _name = 'ir.sequence.strict'
    _description = __doc__

    def get_id(self, cursor, user, clause, context=None):
        cursor.execute('LOCK TABLE "' + self._table + '"')
        return super(SequenceStrict, self).get_id(cursor, user, clause,
                context=context)

SequenceStrict()
