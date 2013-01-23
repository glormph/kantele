import datetime

class BaseParameter(object):
    def __init__(self, name, paramdata):
        self.name = name
        self.store = True
        self.optional = False
        self.selectoptions = None
        self.update_values = False
        self.multiple = False
        self.amount = 1
        self.required_by = None
        self.autodetect_param = False
        self.depends_on = None
        self.inputvalues = []
        self.errors = {}
        self.warnings = {}
        self.is_user = False
        
        self.load_from_conf(paramdata)
    
    def load_from_conf(self, paramdata):
        self.title = paramdata['title']
        if 'values' in paramdata and paramdata['values'] is not None:
            self.selectoptions = [x.encode('utf-8') for x in paramdata['values'] ]
        if 'multiple' in paramdata:
            self.multiple = True
            self.amount = paramdata['multiple']
        if 'optional' in paramdata:
            self.optional = paramdata['optional']
        if 'required_by' in paramdata:
            self.required_by = paramdata['required_by']
        if 'autodetect' in paramdata:
            self.autodetect_param = paramdata['autodetect'] in [1, '1', True,
                'True', 'true']
            self.render_html = self.render_autodetect_html
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
        
        if not self.multiple: # this should only happen in select parameter, I
        #think: MOVE? # no also in checkbox
            if len(self.inputvalues)>1:
                newvals = []
                for val in self.inputvalues:
                    if val not in self.selectoptions:
                        newvals.append(val)
                self.inputvalues = newvals
                self.errors['Conflicting input'] =1

    def render_html(self):
        return False 

    def render_values_html(self):
        html = []
        for value in self.inputvalues:
            html.append("""<div class="metadata_value">{0}
                        </div>""".format(value))
        return html

    def render_autodetect_html(self):
        return False

    def autodetect(self, outfiles, prefix=None):
        if not self.autodetect_param:
            return True
        if prefix == ['None']:
            self.store = False
            return outfiles
        else:
            for fn in outfiles:
                self.errors = {}
                prefix_found = []
                for pref in prefix:
                    if pref in fn:
                        prefix_found.append(pref)
                        # tmp register the pref
                # if two nrs: complain
                # else: 
                # get nr by char-by-char checking validity
                
                cur = fn.index(prefix_found[0]) + len(prefix_found[0])
                while fn[cur] in [' ', '-', '_', '.']:
                    cur += 1
                start = cur
                while not self.errors:
                    if self.inputvalues:
                        outfiles[fn][self.name] = self.inputvalues[0]
                    self.inputvalues = [fn[start:cur+1]]
                    self.validate()
                    cur += 1
            return outfiles


class CheckBoxParameter(BaseParameter):
    def __init__(self, name, paramdata):
        super(CheckBoxParameter, self).__init__(name, paramdata)
        self.multiple = True # Cannot be multiplexed by design, is already multiple
        self.optional = True

    def render_html(self):
        if self.inputvalues:
            values = self.inputvalues
        else:
            values = ['']
        
        base_html ="""<div class="infokey">{0}</div><div class="tablecell"
        id="metafield">""".format(self.title)
        base_html = """{0} <input type="hidden" name="{1}" value="other">
        """.format(base_html, self.name)
        for selectoption in self.selectoptions:
            base_html = """{0} <input type="checkbox" name="{1}"
            value="{2}" {3}> {2}""".format(base_html, self.name, selectoption,
            'checked' if selectoption in values else '')

        return '{0}</div>'.format(base_html)


class TextParameter(BaseParameter):
    def render_html(self):
        if self.inputvalues:
            values = self.inputvalues
        else:
            values = [''] * self.amount
        input_units = []
        for value in values:
            input_units.append("""<div id="{0}"><input type="text" class="infonew"
                    name="{0}" value="{1}"></div>""".format(self.name, value))
        base_html ="""<div class="tablecell" id="metafield">{0}</div>
        """.format(''.join(input_units))
        return base_html
        
    def validate(self):
        super(TextParameter, self).validate()
        self.check_format()

    def check_format(self):
        return True


class SelectParameter(BaseParameter):
    def __init__(self, name, paramdata ):
        super(SelectParameter, self).__init__(name, paramdata)
        if 'selected' in paramdata:
            self.selected = paramdata['selected']
        else:
            self.selected = None
        self.update_values = True
        if 'update_values' in paramdata:            
            self.update_values = paramdata['update_values']

    def render_html(self):
        print self.inputvalues
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
            
            input_unit = """<div id="{0}"><div id="{0}_inputunit0"><select class="infoselect" name="{0}">
        <option value="other" {1}>Other: </option>""".format(self.name,
                'selected' if self.selected==None else '')
            for selectoption in self.selectoptions:
                input_unit = """{0}
                    <option value="{1}" {2}>{1}</option>""".format(input_unit,
                    selectoption, 'selected' if self.selected==selectoption else '')
            input_unit = """{0}
                </select><input type="text" class="infonew" name="{1}"
                value="{2}"></div></div>
                """.format(input_unit, self.name, 
                    value if self.selected==None else '')
            input_units.append(input_unit)
        
        # construct base html
        base_html ="""<div class="tablecell" id="metafield">{1}
        """.format(self.title, ''.join(input_units) )
        if self.multiple:
            base_html = """{0}
            <input type="button" value="Add another {1}" onClick="addField('{2}');">
            </div>""".format(base_html, self.title, self.name)
        else:
            base_html = """{0}</div>""".format(base_html)
        return base_html
    

class DateParameter(TextParameter):
    def validate(self):
        super(DateParameter, self).validate()
        for date in self.inputvalues:
            if date == 'today':
                date = datetime.date.strftime(datetime.datetime.now(), '%Y%m%d')
            if date == 'yesterday':
                date = datetime.date.strftime(datetime.datetime.now()- \
                            datetime.timedelta(1), '%Y%m%d')
            try:
                datediff = datetime.datetime.now() - date
            except TypeError:
                pass # format error caught in check_format, not here
            else:
                if -5 < datediff < 0:
                    self.warnings['Date is in the future. Sure that is ok?'] = 1
                elif datediff < -10:
                    self.errors['Date is more than 10 days in the future. \
                    Surely you cannot be running that long an experiment?'] = 1
        
    def check_format(self):
        try:
            self.inputvalues = [datetime.datetime.strptime(x, '%Y%m%d') for x \
            in self.inputvalues]
        except ValueError:
            self.errors['Wrongly formatted date, use YYYYMMDD'] = 1


class RangeParameter(TextParameter):
    rangeseparator = '-'
    def check_format(self):
        checked_input = []
        for rangeinput in self.inputvalues:
            inval = [x.strip().replace(',', '.') for x in \
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
            self.inputvalues = [float(x) for x in self.inputvalues ]
        except ValueError:
            self.errors['Wrongly formatted {0}. Be sure to write \
                numbers, decimal points are accepted.'.format(self.title)] = 1


class IntegerParameter(TextParameter):
    def check_format(self):
        try:
            self.inputvalues = [int(x) for x in self.inputvalues ]
        except ValueError:
            self.errors['Wrongly formatted {0}. Be sure to write \
                whole numbers, without decimal points'.format(self.title)] = 1


class UserParameter(SelectParameter):
    def __init__(self, name, paramdata):
        super(UserParameter, self).__init__(name, paramdata)
        self.is_user = True 


jsonparams_to_class_map = {
    'user'      :   UserParameter,
    'select'    :   SelectParameter,
    'text'      :   TextParameter,
    'float'     :   FloatParameter,
    'integer'   :   IntegerParameter,
    'xofy'      :   XofYParameter,
    'range'     :   RangeParameter,
    'checkboxes':   CheckBoxParameter,
    'date'      :   DateParameter
    }
