#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import copy
from trytond.model import fields
from trytond.pool import Pool
from trytond.pyson import PYSONEncoder
from trytond.transaction import Transaction


class Model(object):
    """
    Define a model in Tryton.
    """
    _name = None
    _inherits = {}
    _description = ''
    pool = None #XXX change to avoid collision with field
    __columns = None
    __xxx2many_targets = None
    __defaults = None
    _rec_name = 'name'

    id = fields.Integer('ID', readonly=True)

    def _reset_columns(self):
        self.__columns = None
        self._reset_xxx2many_targets()

    def _getcolumns(self):
        if self.__columns:
            return self.__columns
        res = {}
        for attr in dir(self):
            if attr.startswith('_'):
                continue
            if isinstance(getattr(self, attr), fields.Field):
                res[attr] = getattr(self, attr)
        self.__columns = res
        return res

    #replace by _fields
    _columns = property(fget=_getcolumns)

    def _reset_defaults(self):
        self.__defaults = None

    def _getdefaults(self):
        if self.__defaults:
            return self.__defaults
        res = {}
        fields_names = self._columns.keys()
        fields_names += self._inherit_fields.keys()
        for field_name in fields_names:
            if getattr(self, 'default_' + field_name, False):
                res[field_name] = getattr(self, 'default_' + field_name)
        self.__defaults = res
        return res

    _defaults = property(fget=_getdefaults)

    def __new__(cls):
        Pool.register(cls, type='model')

    def __init__(self):
        super(Model, self).__init__()
        self._rpc = {
            'default_get': False,
            'fields_get': False,
        }
        self._inherit_fields = []
        self._error_messages = {}
        # reinit the cache on _columns and _defaults
        self.__columns = None
        self.__defaults = None

        if not self._description:
            self._description = self._name

        self._inherits_reload()
        for k in self._defaults:
            assert (k in self._columns) or (k in self._inherit_fields), \
            'Default function defined in %s but field %s does not exist!' % \
                (self._name, k,)

        for field_name in self._columns.keys() + self._inherit_fields.keys():
            if field_name in self._columns:
                field = self._columns[field_name]
            else:
                field = self._inherit_fields[field_name][2]
            if isinstance(field, (fields.Selection, fields.Reference)) \
                    and not isinstance(field.selection, (list, tuple)) \
                    and field.selection not in self._rpc:
                self._rpc[field.selection] = False
            if field.on_change:
                on_change = 'on_change_' + field_name
                if on_change not in self._rpc:
                    self._rpc[on_change] = False
            if field.on_change_with:
                on_change_with = 'on_change_with_' + field_name
                if on_change_with not in self._rpc:
                    self._rpc[on_change_with] = False

    def __getattr__(self, name):
        # Search if a function exists in inherits parents
        for model_name, field_name in self._inherits.iteritems():
            model_obj = self.pool.get(model_name)
            if hasattr(model_obj, name) and \
                    callable(getattr(model_obj, name)):
                return getattr(model_obj, name)
        raise AttributeError

    def _inherits_reload(self):
        """
        Reconstruct _inherit_fields
        """
        res = {}
        for model in self._inherits:
            res.update(self.pool.get(model)._inherit_fields)
            for field_name in self.pool.get(model)._columns.keys():
                res[field_name] = (model, self._inherits[model],
                        self.pool.get(model)._columns[field_name])
            for field_name in self.pool.get(model)._inherit_fields.keys():
                res[field_name] = (model, self._inherits[model],
                        self.pool.get(model)._inherit_fields[field_name][2])
        self._inherit_fields = res
        self._reset_xxx2many_targets()
        # Update objects that uses this one to update their _inherits fields
        for obj_name in self.pool.object_name_list():
            obj = self.pool.get(obj_name)
            if self._name in obj._inherits:
                obj._inherits_reload()

    def _reset_xxx2many_targets(self):
        self.__xxx2many_targets = None

    def _getxxx2many_targets(self):
        if self.__xxx2many_targets:
            return self.__xxx2many_targets
        to_cache = True

        res = [(field_name, field.model_name)
                for field_name, field in self._columns.iteritems()
                if field._type == 'one2many']

        for field_name, field in self._columns.iteritems():
            if field._type != 'many2many':
                continue
            if hasattr(field, 'get_target'):
                try:
                    model_name = field.get_target(self.pool)._name
                except KeyError:
                    to_cache = False
                    continue
            else:
                model_name = field.model_name
            res.append((field_name, model_name))

        res += [(field_name, field.model_name)
                for _, (_, field_name, field) in \
                        self._inherit_fields.iteritems()
                if field._type == 'one2many']

        for _, (_, field_name, field) in self._inherit_fields.iteritems():
            if field._type != 'many2many':
                continue
            if hasattr(field, 'get_target'):
                try:
                    model_name = field.get_target(self.pool)._name
                except KeyError:
                    to_cache = False
                    continue
            else:
                model_name = field.model_name
            res.append((field_name, model_name))

        if to_cache:
            self.__xxx2many_targets = res
        return res

    _xxx2many_targets = property(fget=_getxxx2many_targets)

    def init(self, module_name):
        """
        Add model in ir.model and ir.model.field.

        :param module_name: the module name
        """

        cursor = Transaction().cursor
        # Add model in ir_model
        cursor.execute("SELECT id FROM ir_model WHERE model = %s",
                (self._name,))
        model_id = None
        if cursor.rowcount == -1 or cursor.rowcount is None:
            data = cursor.fetchone()
            if data:
                model_id, = data
        elif cursor.rowcount != 0:
            model_id, = cursor.fetchone()
        if not model_id:
            cursor.execute("INSERT INTO ir_model " \
                    "(model, name, info, module) VALUES (%s, %s, %s, %s)",
                    (self._name, self._description, self.__doc__,
                        module_name))
            cursor.execute("SELECT id FROM ir_model WHERE model = %s",
                    (self._name,))
            (model_id,) = cursor.fetchone()
        else:
            cursor.execute('UPDATE ir_model ' \
                    'SET name = %s, ' \
                        'info = %s ' \
                    'WHERE id = %s',
                    (self._description, self.__doc__, model_id))

        # Update translation of model
        for name, src in [(self._name + ',name', self._description)]:
            cursor.execute('SELECT id FROM ir_translation ' \
                    'WHERE lang = %s ' \
                        'AND type = %s ' \
                        'AND name = %s ' \
                        'AND res_id = %s',
                    ('en_US', 'model', name, 0))
            trans_id = None
            if cursor.rowcount == -1 or cursor.rowcount is None:
                data = cursor.fetchone()
                if data:
                    trans_id, = data
            elif cursor.rowcount != 0:
                trans_id, = cursor.fetchone()
            if not trans_id:
                cursor.execute('INSERT INTO ir_translation ' \
                        '(name, lang, type, src, value, module, fuzzy) ' \
                        'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                        (name, 'en_US', 'model', src, '', module_name, False))
            else:
                cursor.execute('UPDATE ir_translation ' \
                        'SET src = %s ' \
                        'WHERE id = %s',
                        (src, trans_id))

        # Add field in ir_model_field and update translation
        cursor.execute('SELECT f.id AS id, f.name AS name, ' \
                    'f.field_description AS field_description, ' \
                    'f.ttype AS ttype, f.relation AS relation, ' \
                    'f.module as module, f.help AS help '\
                'FROM ir_model_field AS f, ir_model AS m ' \
                'WHERE f.model = m.id ' \
                    'AND m.model = %s ',
                        (self._name,))
        model_fields = {}
        for field in cursor.dictfetchall():
            model_fields[field['name']] = field

        # Prefetch field translations
        if self._columns:
            cursor.execute('SELECT id, name, src, type FROM ir_translation ' \
                    'WHERE lang = %s ' \
                        'AND type IN (%s, %s, %s) ' \
                        'AND name IN ' \
                            '(' + ','.join(('%s',) * len(self._columns)) + ')',
                            ('en_US', 'field', 'help', 'selection') + \
                                    tuple([self._name + ',' + x \
                                        for x in self._columns]))
        trans_fields = {}
        trans_help = {}
        trans_selection = {}
        for trans in cursor.dictfetchall():
            if trans['type'] == 'field':
                trans_fields[trans['name']] = trans
            elif trans['type'] == 'help':
                trans_help[trans['name']] = trans
            elif trans['type'] == 'selection':
                trans_selection.setdefault(trans['name'], {})
                trans_selection[trans['name']][trans['src']] = trans

        for field_name in self._columns:
            field = self._columns[field_name]
            relation = ''
            if hasattr(field, 'model_name'):
                relation = field.model_name
            elif hasattr(field, 'relation_name'):
                relation = field.relation_name
            if field_name not in model_fields:
                cursor.execute("INSERT INTO ir_model_field " \
                        "(model, name, field_description, ttype, " \
                            "relation, help, module) " \
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (model_id, field_name, field.string, field._type,
                            relation, field.help, module_name))
            elif model_fields[field_name]['field_description'] != field.string \
                    or model_fields[field_name]['ttype'] != field._type \
                    or model_fields[field_name]['relation'] != relation \
                    or model_fields[field_name]['help'] != field.help:
                cursor.execute('UPDATE ir_model_field ' \
                        'SET field_description = %s, ' \
                            'ttype = %s, ' \
                            'relation = %s, ' \
                            'help = %s ' \
                        'WHERE id = %s ',
                        (field.string, field._type, relation,
                            field.help, model_fields[field_name]['id']))
            trans_name = self._name + ',' + field_name
            if trans_name not in trans_fields:
                if field_name not in ('create_uid', 'create_date',
                            'write_uid', 'write_date', 'id'):
                    cursor.execute('INSERT INTO ir_translation ' \
                            '(name, lang, type, src, value, module, fuzzy) ' \
                            'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                            (trans_name, 'en_US', 'field',
                                field.string, '', module_name, False))
            elif trans_fields[trans_name]['src'] != field.string:
                cursor.execute('UPDATE ir_translation ' \
                        'SET src = %s ' \
                        'WHERE id = %s ',
                        (field.string, trans_fields[trans_name]['id']))
            if trans_name not in trans_help:
                if field.help:
                    cursor.execute('INSERT INTO ir_translation ' \
                            '(name, lang, type, src, value, module, fuzzy) ' \
                            'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                            (trans_name, 'en_US', 'help',
                                field.help, '', module_name, False))
            elif trans_help[trans_name]['src'] != field.help:
                cursor.execute('UPDATE ir_translation ' \
                        'SET src = %s ' \
                        'WHERE id = %s ',
                        (field.help, trans_help[trans_name]['id']))
            if hasattr(field, 'selection') \
                    and isinstance(field.selection, (tuple, list)) \
                    and ((hasattr(field, 'translate_selection') \
                        and field.translate_selection)
                        or not hasattr(field, 'translate_selection')):
                for (_, val) in field.selection:
                    if trans_name not in trans_selection \
                            or val not in trans_selection[trans_name]:
                        cursor.execute('INSERT INTO ir_translation ' \
                                '(name, lang, type, src, value, ' \
                                    'module, fuzzy) ' \
                                'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                                (trans_name, 'en_US', 'selection', val, '',
                                    module_name, False))
        # Clean ir_model_field from field that are no more existing.
        for field_name in model_fields:
            if model_fields[field_name]['module'] == module_name \
                    and field_name not in self._columns:
                #XXX This delete field even when it is defined later
                # in the module
                cursor.execute('DELETE FROM ir_model_field '\
                                   'WHERE id = %s',
                               (model_fields[field_name]['id'],))

        # Add error messages in ir_translation
        cursor.execute('SELECT id, src FROM ir_translation ' \
                'WHERE lang = %s ' \
                    'AND type = %s ' \
                    'AND name = %s',
                ('en_US', 'error', self._name))
        trans_error = {}
        for trans in cursor.dictfetchall():
            trans_error[trans['src']] = trans

        errors = self._get_error_messages()
        for error in set(errors):
            if error not in trans_error:
                cursor.execute('INSERT INTO ir_translation ' \
                        '(name, lang, type, src, value, module, fuzzy) ' \
                        'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                        (self._name, 'en_US', 'error', error, '', module_name,
                            False))

    def _get_error_messages(self):
        return self._error_messages.values()

    def raise_user_error(self, error, error_args=None,
            error_description='', error_description_args=None,
            raise_exception=True):
        '''
        Raise an exception that will be displayed as an error message
        in the client.

        :param error: the key of the dictionary _error_messages used
            for error message
        :param error_args: the arguments that will be used
            for "%"-based substitution
        :param error_description: the key of the dictionary
            _error_messages used for error description
        :param error_description_args: the arguments that will be used
            for "%"-based substitution
        :param raise_exception: if set to False return the error string
            (or tuple if error_description is not empty) instead of raising an
            exception.
        '''
        translation_obj = self.pool.get('ir.translation')

        error = self._error_messages.get(error, error)

        language = Transaction().context.get('language') or 'en_US'
        res = translation_obj._get_source(self._name, 'error', language, error)
        if not res:
            res = translation_obj._get_source(error, 'error', language)
        if not res:
            res = translation_obj._get_source(error, 'error', 'en_US')

        if res:
            error = res

        if error_args:
            try:
                error = error % error_args
            except TypeError:
                pass

        if error_description:
            error_description = self._error_messages.get(error_description,
                    error_description)

            res = translation_obj._get_source(self._name, 'error', language,
                    error_description)
            if not res:
                res = translation_obj._get_source(error_description, 'error',
                        language)
            if not res:
                res = translation_obj._get_source(error_description, 'error',
                        'en_US')

            if res:
                error_description = res

            if error_description_args:
                try:
                    error_description = error_description % \
                            error_description_args
                except TypeError:
                    pass
            if raise_exception:
                raise Exception('UserError', error, error_description)
            else:
                return (error, error_description)
        if raise_exception:
            raise Exception('UserError', error)
        else:
            return error

    def raise_user_warning(self, warning_name, warning,
            warning_args=None, warning_description='',
            warning_description_args=None):
        '''
        Raise an exception that will be displayed as a warning message
        in the client, if the user has not yet bypassed it.

        :param warning_name: the unique warning name
        :param warning: the key of the dictionary _error_messages used
            for warning message
        :param warning_args: the arguments that will be used for
            "%"-based substitution
        :param warning_description: the key of the dictionary
            _error_messages used for warning description
        :param warning_description_args: the arguments that will be used
            for "%"-based substitution
        '''
        warning_obj = self.pool.get('res.user.warning')
        if warning_obj.check(warning_name):
            if warning_description:
                warning, warning_description = self.raise_user_error(warning,
                        error_args=warning_args,
                        error_description=warning_description,
                        error_description_args=warning_description_args,
                        raise_exception=False)
                raise Exception('UserWarning', warning_name, warning,
                        warning_description)
            else:
                warning = self.raise_user_error(warning,
                        error_args=warning_args, raise_exception=False)
                raise Exception('UserWarning', warning_name, warning)

    def default_get(self, fields_names, with_rec_name=True):
        '''
        Return a dict with the default values for each field in fields_names.

        :param fields_names: a list of fields names
        :param with_rec_name: a boolean to add rec_name value
        :return: a dictionary with field name as key
            and default value as value
        '''
        property_obj = self.pool.get('ir.property')
        ir_default_obj = self.pool.get('ir.default')
        value = {}

        # get the default values defined in the object
        for field_name in fields_names:
            if field_name in self._defaults:
                value[field_name] = self._defaults[field_name]()
            if field_name in self._columns:
                field = self._columns[field_name]
            else:
                field = self._inherit_fields[field_name][2]
            if (field._type == 'boolean'
                    and not field_name in value):
                value[field_name] = False
            if isinstance(field, fields.Property):
                value[field_name] = property_obj.get(field_name, self._name)
            if (with_rec_name
                    and field._type in ('many2one',)
                    and value.get(field_name)):
                obj = self.pool.get(field.model_name)
                if 'rec_name' in obj._columns:
                    value[field_name + '.rec_name'] = obj.browse(
                        value[field_name]).rec_name

        # get the default values set by the user and override the default
        # values defined in the object
        for name in (self._inherits.keys() + [self._name]):
            defaults = ir_default_obj.get_default(name, False)
            for field_name, field_value in defaults.items():
                if field_name in fields_names:
                    if field_name in self._columns:
                        field = self._columns[field_name]
                    else:
                        field = self._inherit_fields[field_name][2]
                    if field._type in ('many2one', 'one2one'):
                        if not isinstance(field_value, (int, long)):
                            continue
                        obj = self.pool.get(field.model_name)
                        if not hasattr(obj, 'search') \
                                or not obj.search([
                                    ('id', '=', field_value),
                                    ]):
                            continue
                        if with_rec_name and 'rec_name' in obj._columns:
                            value[field_name + '.rec_name'] = obj.browse(
                                    field_value).rec_name
                    if field._type in ('many2many'):
                        if not isinstance(field_value, list):
                            continue
                        obj = field.get_target(self.pool)
                        field_value2 = []
                        for i in range(len(field_value)):
                            if not hasattr(obj, 'search') \
                                    or not obj.search([
                                        ('id', '=', field_value[i]),
                                        ]):
                                continue
                            field_value2.append(field_value[i])
                        field_value = field_value2
                    if field._type in ('one2many'):
                        if not isinstance(field_value, list):
                            continue
                        obj = self.pool.get(field.model_name)
                        field_value2 = []
                        for i in range(len(field_value or [])):
                            field_value2.append({})
                            for field2 in field_value[i].keys():
                                if (field2 in obj._columns
                                        and obj._columns[field2]._type
                                        in ('many2one',)):
                                    obj2 = self.pool.get(
                                            obj._columns[field2].model_name)
                                    if not hasattr(obj2, 'search'):
                                        continue
                                    if not obj2.search([
                                        ('id', '=', field_value[i][field2]),
                                        ]):
                                        continue
                                    if (with_rec_name
                                            and 'rec_name' in obj2._columns):
                                        field_value[i][field2 + '.rec_name'] = (
                                                obj2.browse(
                                                    field_value[i][field2],
                                                    ).rec_name)
                                # TODO add test for many2many and one2many
                                field_value2[i][field2] = field_value[i][field2]
                        field_value = field_value2
                    value[field_name] = field_value
        value = self._default_on_change(value)
        if not with_rec_name:
            for field in value.keys():
                if field.endswith('.rec_name'):
                    del value[field]
        return value

    def _default_on_change(self, value):
        """
        Call on_change function for the default value
        and return new default value

        :param value: a dictionnary with the default value
        :return: a new dictionnary of default value
        """
        res = value.copy()
        val = {}
        for i in self._inherits.keys():
            val.update(self.pool.get(i)._default_on_change(value))
        for field in value.keys():
            if field in self._columns:
                if self._columns[field].on_change:
                    args = {}
                    for arg in self._columns[field].on_change:
                        args[arg] = value.get(arg, False)
                        if arg in self._columns \
                                and self._columns[arg]._type == 'many2one':
                            if isinstance(args[arg], (list, tuple)):
                                args[arg] = args[arg][0]
                    val.update(getattr(self, 'on_change_' + field)(args))
                if self._columns[field]._type in ('one2many',):
                    obj = self.pool.get(self._columns[field].model_name)
                    for val2 in res[field]:
                        val2.update(obj._default_on_change(val2))
        res.update(val)
        return res

    def fields_get(self, fields_names=None):
        """
        Return the definition of each field on the model.

        :param fields_names: a list of field names or None for all fields
        :return: a dictionary with field name as key and definition as value
        """
        res = {}
        translation_obj = self.pool.get('ir.translation')
        model_access_obj = self.pool.get('ir.model.access')
        field_access_obj = self.pool.get('ir.model.field.access')

        for parent in self._inherits:
            res.update(self.pool.get(parent).fields_get(fields_names))
        write_access = model_access_obj.check(self._name, 'write',
                raise_exception=False)

        #Add translation to cache
        language = Transaction().context.get('language') or 'en_US'
        trans_args = []
        for field in (x for x in self._columns.keys()
                if ((not fields_names) or x in fields_names)):
            trans_args.append((self._name + ',' + field, 'field', language,
                None))
            trans_args.append((self._name + ',' + field, 'help', language,
                None))
            if hasattr(self._columns[field], 'selection'):
                if isinstance(self._columns[field].selection, (tuple, list)) \
                        and ((hasattr(self._columns[field],
                            'translate_selection') \
                            and self._columns[field].translate_selection) \
                            or not hasattr(self._columns[field],
                                'translate_selection')):
                    sel = self._columns[field].selection
                    for (key, val) in sel:
                        trans_args.append((self._name + ',' + field,
                            'selection', language, val))
        translation_obj._get_sources(trans_args)

        encoder = PYSONEncoder()

        fwrite_accesses = field_access_obj.check(self._name, fields_names or
                self._columns.keys(), 'write', access=True)
        for field in (x for x in self._columns.keys()
                if ((not fields_names) or x in fields_names)):
            res[field] = {'type': self._columns[field]._type}
            for arg in (
                    'string',
                    'readonly',
                    'states',
                    'size',
                    'required',
                    'change_default',
                    'translate',
                    'help',
                    'select',
                    'on_change',
                    'add_remove',
                    'on_change_with',
                    'sort',
                    'datetime_field',
                    'loading',
                    ):
                if getattr(self._columns[field], arg, None) != None:
                    res[field][arg] = copy.copy(getattr(self._columns[field],
                        arg))
            if not write_access or not fwrite_accesses.get(field, True):
                res[field]['readonly'] = True
                if res[field].get('states') and \
                        'readonly' in res[field]['states']:
                    del res[field]['states']['readonly']
            for arg in ('digits', 'invisible'):
                if hasattr(self._columns[field], arg) \
                        and getattr(self._columns[field], arg):
                    res[field][arg] = copy.copy(getattr(self._columns[field],
                        arg))
            if isinstance(self._columns[field],
                    (fields.Function, fields.One2Many)) \
                    and not self._columns[field].order_field:
                res[field]['sortable'] = False

            if Transaction().context.get('language'):
                # translate the field label
                res_trans = translation_obj._get_source(
                        self._name + ',' + field, 'field',
                        Transaction().context['language'])
                if res_trans:
                    res[field]['string'] = res_trans
                help_trans = translation_obj._get_source(
                        self._name + ',' + field, 'help',
                        Transaction().context['language'])
                if help_trans:
                    res[field]['help'] = help_trans

            if hasattr(self._columns[field], 'selection'):
                if isinstance(self._columns[field].selection, (tuple, list)):
                    sel = copy.copy(self._columns[field].selection)
                    if Transaction().context.get('language') and \
                            ((hasattr(self._columns[field],
                                'translate_selection') \
                                and self._columns[field].translate_selection) \
                                or not hasattr(self._columns[field],
                                    'translate_selection')):
                        # translate each selection option
                        sel2 = []
                        for (key, val) in sel:
                            val2 = translation_obj._get_source(
                                    self._name + ',' + field, 'selection',
                                    language, val)
                            sel2.append((key, val2 or val))
                        sel = sel2
                    res[field]['selection'] = sel
                else:
                    # call the 'dynamic selection' function
                    res[field]['selection'] = copy.copy(
                            self._columns[field].selection)
            if res[field]['type'] in (
                    'one2many',
                    'many2many',
                    'many2one',
                    'one2one',
                    ):
                if hasattr(self._columns[field], 'model_name'):
                    relation = copy.copy(self._columns[field].model_name)
                else:
                    relation = copy.copy(self._columns[field].get_target(
                        self.pool)._name)
                res[field]['relation'] = relation
                res[field]['domain'] = copy.copy(self._columns[field].domain)
                res[field]['context'] = copy.copy(self._columns[field].context)
            if res[field]['type'] == 'one2many' \
                    and hasattr(self._columns[field], 'field'):
                res[field]['relation_field'] = copy.copy(
                        self._columns[field].field)

            # convert attributes into pyson
            for attr in ('states', 'domain', 'context', 'digits', 'add_remove'):
                if attr in res[field]:
                    res[field][attr] = encoder.encode(res[field][attr])

        if fields_names:
            # filter out fields which aren't in the fields_names list
            for i in res.keys():
                if i not in fields_names:
                    del res[i]
        return res
