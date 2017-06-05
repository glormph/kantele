import datetime
from django.contrib.auth.models import User


class BaseParameter(object):
    def __init__(self, name, paramdata):
        self.name = name
        self.store = True
        self.optional = False
        self.update_values = False  # FIXME deprecate?
        self.required_by = None
        self.autodetect_param = False
        self.hidden_param = False
        self.depends_on = None
        self.inputvalues = []
        self.errors = {}
        self.warnings = {}
        self.is_lookup = False
        self.is_user = False
        self.is_owner = False

        self.multiple = False
        self.amount = 1

        self.load_from_conf(paramdata)

    def load_from_conf(self, paramdata):
        self.title = paramdata['title']
        if 'values' in paramdata and paramdata['values'] is not None:
            self.selectoptions = [x for x in paramdata['values']]
        if 'multiple' in paramdata:
            self.multiple = True
            self.amount = paramdata['multiple']
        if 'optional' in paramdata:
            self.optional = paramdata['optional']
        if 'required_by' in paramdata:
            self.required_by = paramdata['required_by']
        if 'hidden' in paramdata:
            self.hidden_param = paramdata['hidden'] in [1, '1', True, 'True',
                                                        'true']
        if 'autodetect' in paramdata:
            self.autodetect_param = paramdata['autodetect'] in [1, '1', True,
                                                                'True', 'true']
            self.render_html = self.render_no_html
        if 'depends_on' in paramdata:
            self.depends_on = paramdata['depends_on']

    def check_format(self):
        return True

    def validate(self):
        processed_input = []
        for inval in self.inputvalues:
            if inval not in ['', 'other']:
                processed_input.append(inval)
        self.inputvalues = processed_input

        if not self.inputvalues:
            if self.optional or self.required_by:
                self.store = False
            else:
                self.errors['Field {0} is required.'.format(self.title)] = 1
        if not self.multiple:  # this should only happen in select parameter, I
        #think: MOVE? # no also in checkbox
            if len(self.inputvalues) > 1:
                newvals = []
                for val in self.inputvalues:
                    if val not in self.selectoptions:
                        newvals.append(val)
                self.inputvalues = newvals
                self.errors['Conflicting input'] = 1

    def render_html(self):
        return False

    def render_values_html(self):
        html = []
        for value in self.inputvalues:
            html.append("""<div class="metadata_value">{0}
                        </div>""".format(value))
        return ''.join(html)

    def render_no_html(self):
        return False

    def autodetect(self, files, filelist, prefix=None):
        if not self.autodetect_param:
            return True
        self.store = False  # autodetect params are not saved in metadata, but
        # in files record in DB
        if prefix == ['None']:
            # In case of no (fraction or other) prefix in filename
            return files, False
        else:
            for fn in filelist:
                self.errors = {}
                prefix_found = []
                self.inputvalues = []
                for pref in prefix:
                    # inputvalues is list
                    if pref in fn:
                        prefix_found.append(pref)

                # if two nrs: complain - shouldnt happen, errors checked
                # before autodetection
                # else:
                # get nr by char-by-char checking validity(below)

                cur = fn.index(prefix_found[0]) + len(prefix_found[0])
                while fn[cur] in [' ', '-', '_', '.']:
                    cur += 1
                start = cur
                while not self.errors:
                    if self.inputvalues:
                        files[fn][self.name] = self.inputvalues[0]
                    if len(fn) < cur + 1:
                        break
                    else:
                        self.inputvalues = [fn[start:cur + 1]]
                    self.validate()  # populates self.errors in case of error
                                     # in inputvalues
                    cur += 1
                if cur - start == 1 and self.errors:
                    # no value found after prefix
                    files[fn][self.name] = 'NA'
            autodetection_done = True
            return files, autodetection_done


class CheckBoxParameter(BaseParameter):
    def __init__(self, name, paramdata):
        super(CheckBoxParameter, self).__init__(name, paramdata)
        self.multiple = True  # Cannot be multiplexed, is already multiple
        self.optional = True

    def render_html(self):
        if self.inputvalues:
            values = self.inputvalues
        else:
            values = ['']
        base_html = """<input type="hidden" name="{0}" value="other">
        """.format(self.name)
        for selectoption in self.selectoptions:
            base_html = """{0} <input type="checkbox" name="{1}"
            value="{2}" {3}> {2}""".format(base_html, self.name, selectoption,
                                           'checked' if selectoption in
                                           values else '')

        return base_html


class TextParameter(BaseParameter):
    def render_html(self):
        if self.inputvalues:
            values = self.inputvalues
        else:
            values = [''] * self.amount
        input_units = []
        for value in values:
            input_units.append(
                """<div id="{0}"><div id="{0}_inputunit0">
                   <input type="text" class="textinput" name="{0}" value="{1}">
                   </div></div>""".format(self.name, value))
        return ''.join(input_units)

    def validate(self):
        super(TextParameter, self).validate()
        self.check_format()

    def check_format(self):
        return True


class SelectParameter(BaseParameter):
    def __init__(self, name, paramdata):
        super(SelectParameter, self).__init__(name, paramdata)
        self.select_and_text = True
        if 'notext' in paramdata and paramdata['notext'] in [1, '1', True,
                                                             'True', 'true']:
            self.select_and_text = False
        if 'selected' in paramdata:
            self.selected = paramdata['selected']
        else:
            self.selected = None

        # FIXME update_values: to be deprecated?
        self.update_values = True
        if 'update_values' in paramdata:
            self.update_values = paramdata['update_values']

    def render_html(self):
        if self.inputvalues:
            values = self.inputvalues
        else:
            values = [''] * self.amount

        # first define input
        input_units = []
        for value in values:
            if value in self.selectoptions:
                self.selected = value
            elif value != '':
                self.selected = None

            input_unit = """<div id="{0}"><div id="{0}_inputunit0"><select
            class="selectinput" name="{0}">""".format(self.name)
            if self.select_and_text:
                input_unit += ('<option value="other" {0}>Other: '
                               '</option>'.format('selected' if
                                                  self.selected is None
                                                  else ''))
            for selectoption in self.selectoptions:
                input_unit += ('option value="{0}" {1}>{0}'
                               '</option>'.format(selectoption, 'selected'
                                                  if self.selected ==
                                                  selectoption else ''))
            if self.select_and_text:
                input_unit += ('</select><input type="text" class="textinput" '
                               'name="{0}" value="{1}">'
                               '</div>'.format(self.name, value
                                               if self.selected is None
                                               else ''))
            else:
                input_unit += """</select></div>"""
            input_units.append(input_unit)

        # construct base html
        base_html = ''.join(input_units)
        if self.multiple:
            base_html += """</div><input type="button" value="Add another {0}"
            onClick="addField('{1}');">""".format(self.title, self.name)
        else:
            base_html += """</div>"""
        return base_html


class DateParameter(TextParameter):
    def validate(self):
        super(DateParameter, self).validate()
        for date in self.inputvalues:
            if date == 'today':
                date = datetime.date.strftime(datetime.datetime.now(),
                                              '%Y%m%d')
            if date == 'yesterday':
                date = datetime.date.strftime(datetime.datetime.now() -
                                              datetime.timedelta(1), '%Y%m%d')
            try:
                datediff = datetime.datetime.now() - date
            except TypeError:
                pass  # format error caught in check_format, not here
            else:
                if -5 < datediff < 0:
                    self.warnings['Date is in the future. '
                                  'Sure that is ok?'] = 1
                elif datediff < -10:
                    self.errors['Date is more than 10 days in the future. '
                                'Surely you cannot be running that long '
                                'an experiment?'] = 1

    def check_format(self):
        try:
            self.inputvalues = [datetime.datetime.strptime(x, '%Y%m%d') for x
                                in self.inputvalues]
        except ValueError:
            self.errors['Wrongly formatted date, use YYYYMMDD'] = 1


class RangeParameter(TextParameter):
    rangeseparator = '-'

    def check_format(self):
        checked_input = []
        for rangeinput in self.inputvalues:
            inval = [x.strip().replace(',', '.') for x in
                     rangeinput.split(self.rangeseparator)]
            if len(inval) != 2:
                self.errors['Wrongly formatted {0}. Use "X.xx {1} \
                Y.yy"'.format(self.title, self.rangeseparator)] = 1
            try:
                [float(x) for x in inval]
            except ValueError:
                self.errors['Wrongly formatted {0}. Be sure to write \
                numbers, decimal points are accepted.'.format(self.title)] = 1
            else:
                checked_input.append(inval)


class XofYParameter(RangeParameter):
    rangeseparator = 'of'


class FloatParameter(TextParameter):
    def check_format(self):
        try:
            self.inputvalues = [float(x) for x in self.inputvalues]
        except ValueError:
            self.errors['Wrongly formatted {0}. Be sure to write \
                numbers, decimal points are accepted.'.format(self.title)] = 1


class IntegerParameter(TextParameter):
    def check_format(self):
        try:
            self.inputvalues = [int(x) for x in self.inputvalues]
        except ValueError:
            self.errors['Wrongly formatted {0}. Be sure to write \
                whole numbers, without decimal points'.format(self.title)] = 1


class UserParameter(SelectParameter):
    def __init__(self, name, paramdata):
        super(UserParameter, self).__init__(name, paramdata)
        self.is_user = True
        self.select_and_text = False
        if 'owner' in paramdata and paramdata['owner'] in [1, '1',
                                                           True, 'true']:
            self.is_owner = True
        self.selectoptions = ['{0} {1}'.format(u.first_name.encode('utf-8'),
                                               u.last_name.encode('utf-8'))
                              for u in User.objects.all()]


class LookupParameter(BaseParameter):
    def __init__(self, name, paramdata):
        super(LookupParameter, self).__init__(name, paramdata)
        self.is_lookup = True
        self.keyparam = paramdata['keyparam']
        self.lookup_table = paramdata['lookup']

    def lookup(self, keyparam):
        self.inputvalues = self.lookup_table[keyparam.inputvalues[0]]
        if type(self.inputvalues) in [str, int, float]:
            self.inputvalues = [self.inputvalues]


jsonparams_to_class_map = {
    'user':   UserParameter,
    'select':   SelectParameter,
    'text':   TextParameter,
    'float':   FloatParameter,
    'integer':   IntegerParameter,
    'xofy':   XofYParameter,
    'range':   RangeParameter,
    'checkboxes':   CheckBoxParameter,
    'date':   DateParameter,
    'lookup':   LookupParameter,
}
