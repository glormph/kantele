import json
import parameters
from util import util


class ParameterSet(object):
    def __init__(self):
        self.params = {}
        self.error = False
        # FIXME param_conf, should we only load it upon server start!
        # Or is this a feature with live non-breaking changes?
        with open('param_conf_newest.json') as fp:
            config = json.load(fp)
            config = util.convert_dicts_unicode_to_utf8(config)
        # FIXME here call the DB to get initialization values for each param
        for paramconfig in config:
            self.params[paramconfig] = parameters.jsonparams_to_class_map[
                config[paramconfig]['type']](paramconfig, config[paramconfig])

    def initialize(self, user=None, record=None):
        if record:
            for p in self.params:
                if p not in record:
                    continue
                invals = []
                if type(record[p]) != list:
                    invals.append(record[p])
                else:
                    for value in record[p]:
                        invals.append(value)
                for value in invals:
                    if type(value) == unicode:
                        value = value.encode('utf-8')
                    self.params[p].inputvalues.append(value)

    def get_user_params(self):
        ups = []
        for p in self.params:
            if self.params[p].is_user:
                ups.append(self.params[p])
        return ups

    def incoming_metadata(self, formdata):
        params_passed = [x for x in formdata if x in self.params.keys()]
        # params excluded include:
        # ['csrfmiddlewaretoken', 'step']

        # fill parameters with data and validate input
        for paramname in params_passed:
            check, unique_invals = {}, []
            invals = formdata.getlist(paramname)
            for val in invals:
                if val in check:
                    continue
                check[val] = 1
                unique_invals.append(val)

            self.params[paramname].inputvalues = [x.encode('utf-8') for x
                                                  in unique_invals]

        self.check_incoming_data(params_passed)

    def check_incoming_data(self, params_passed):
        # validate input
        for paramname in params_passed:
            self.params[paramname].validate()
        # check if certain parameters require presence of other parameters
        for paramname in params_passed:
            if self.params[paramname].required_by:
                for reqname, req in self.params[paramname].required_by.items():
                    # check if requiring parameter is filled in, but not
                    # required param
                    if type(req) in [str, unicode]:
                        req = [req]
                    if (self.params[reqname] and
                        any([x in self.params[reqname].inputvalues
                             for x in req])):
                        if self.params[paramname].errors or \
                                not self.params[paramname].store or \
                                not self.params[paramname].inputvalues:
                            self.params[paramname].errors[
                                'Fields belong together: Your input in field '
                                '{0} requires filling in {1}.'.format(
                                    self.params[reqname].title,
                                    self.params[paramname].title)] = 1
                    # check if required param is filled in but not
                    # requiring param
                    if self.params[paramname]:
                        if not self.params[reqname].store or \
                                not self.params[reqname].inputvalues:
                            self.params[paramname].warnings[
                                'Possible orphan field: field {0} is '
                                'required by field {1}, but that has not '
                                'been filled in.'.format(
                                    self.params[paramname].title,
                                    self.params[reqname].title)
                            ] = 1

        # check if any error in any parameter of set
        for paramname in params_passed:
            if self.params[paramname].errors:
                self.error = True

    def do_autodetection(self, files, files_to_process):
        autodetection_done = False
        for p in self.params:
            if self.params[p].autodetect_param:
                prefix = self.params[self.params[p].depends_on].inputvalues
                files, check = self.params[p].autodetect(files,
                                                         files_to_process,
                                                         prefix)
                if check:
                    autodetection_done = True
        return files, autodetection_done

    def parameter_lookup(self):
        for p in self.params:
            if self.params[p].is_lookup:
                k = self.params[self.params[p].keyparam]
                self.params[p].lookup(k)

    def generate_metadata_for_db(self, **kwargs):
        # kwargs will be added to metadata as k/v pairs
        self.metadata = {}
        for p in self.params:
            if self.params[p].store:
                vals = self.params[p].inputvalues
                if len(vals) == 1:
                    vals = vals[0]
                self.metadata[p] = vals
        for p in kwargs:
            self.metadata[p] = kwargs[p]

    def return_dataset_owners(self):
        owners = []
        for p in self.params:
            if self.params[p].is_owner:
                for v in self.params[p].inputvalues:
                    owners.append(v)
        return owners
