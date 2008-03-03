import time
from trytond.osv import fields, OSV


class SequenceType(OSV):
    "Sequence type"
    _name = 'ir.sequence.type'
    _description = __doc__
    name = fields.Char('Sequence Name',size=64, required=True)
    code = fields.Char('Sequence Code',size=32, required=True)

SequenceType()


class Sequence(OSV):
    "Sequence"
    _name = 'ir.sequence'
    _description = __doc__
    name = fields.Char('Sequence Name',size=64, required=True)
    code = fields.Selection('code_get', 'Sequence Code',size=64,
       required=True)
    active = fields.Boolean('Active')
    prefix = fields.Char('Prefix',size=64)
    suffix = fields.Char('Suffix',size=64)
    number_next = fields.Integer('Next Number', required=True)
    number_increment = fields.Integer('Increment Number', required=True)
    padding = fields.Integer('Number padding', required=True)

    def default_active(self, cursor, user, context=None):
        return 1

    def default_number_increment(self, cursor, user, context=None):
        return 1

    def default_number_next(self, cursor, user, context=None):
        return 1

    def default_padding(self, cursor, user, context=None):
        return 0

    def code_get(self, cursor, user, context=None):
        cursor.execute('select code, name from ir_sequence_type')
        return cursor.fetchall()

    def _process(self, string):
        return (string or '') % {
                'year':time.strftime('%Y'),
                'month': time.strftime('%m'),
                'day':time.strftime('%d'),
                }

    def get_id(self, cursor, user, sequence_id, test='id=%s'):
        cursor.execute('lock table ir_sequence')
        cursor.execute('SELECT id, number_next, number_increment, prefix, ' \
                    'suffix, padding ' \
                'FROM ir_sequence ' \
                'WHERE ' + test + ' AND active = True', (sequence_id,))
        res = cursor.dictfetchone()
        if res:
            cursor.execute('UPDATE ir_sequence ' \
                    'SET number_next = number_next + number_increment ' \
                    'WHERE id = %s AND active = True', (res['id'],))
            if res['number_next']:
                return self._process(res['prefix']) + \
                        '%%0%sd' % res['padding'] % res['number_next'] + \
                        self._process(res['suffix'])
            else:
                return self._process(res['prefix']) + \
                        self._process(res['suffix'])
        return False

    def get(self, cursor, user, code):
        return self.get_id(cursor, user, code, test='code=%s')

Sequence()
