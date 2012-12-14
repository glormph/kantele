import json, os, datetime, glob, shutil
import parameters, consts


class ParameterSet(object):
    def __init__(self):
        self.params = {}
        self.error = []
        with open('param_conf_newest.json') as fp:
            config = json.load(fp)
        for paramconfig in config:
            self.params[paramconfig] = parameters.jsonparams_to_class_map[config[paramconfig]['type']](paramconfig, config[paramconfig])
             
    def initialize(self, request):
        username = '{0} {1}'.format(request.user.first_name,
        request.user.last_name)
        for p in self.params:
            if self.params[p].is_user:
                self.params[p].inputvalues = [username]
            
    def incoming_metadata(self, formdata):
        params_passed = [x for x in formdata if x not in \
            ['csrfmiddlewaretoken', 'step', 'tmpdir', 'add_outliers',
             'outlierfiles'] ]
        # fill parameters with data and validate input
        for paramname in params_passed:
            check, unique_invals = {},[]
            invals = formdata.getlist(paramname)
            for val in invals:
                if val in check: continue
                check[val] = 1
                unique_invals.append(val)

            self.params[paramname].inputvalues = [x.encode('utf-8') for x in unique_invals]

        self.tmpdir = formdata['tmpdir'] 
        self.check_incoming_data(params_passed)
        self.is_outlier = formdata['step'] == 'outlier_meta'
        self.add_outliers = formdata['add_outliers'] in ['True', 'true', 1,
        '1', True]
        with open(os.path.join(self.tmpdir, 'filelist.json')) as fp:
            self.allfiles = json.load(fp)
        
        if self.is_outlier:
            self.outlierfiles = formdata.getlist('outlierfiles')
            

    def check_incoming_data(self, params_passed):
        # validate input
        for paramname in params_passed:
            self.params[paramname].validate()
        # check if certain parameters require presence of other parameters
        for paramname in params_passed:
            if self.params[paramname].required_by:
                requirement = self.params[paramname].required_by
                for reqname in requirement:
                    # check if requiring parameter is filled in, but not the required
                    if type(requirement[reqname]) in [str, unicode]:
                        requirement[reqname] = [requirement[reqname]]
                    print requirement[reqname], self.params[reqname].inputvalues
                    if self.params[reqname] and \
                        True in [x in self.params[reqname].inputvalues for x in \
                        requirement[reqname]]:
                        if self.params[paramname].errors or \
                                not self.params[paramname].store or \
                                not self.params[paramname].inputvalues:
                            self.params[paramname].errors['Fields belong \
        together: Your input in field {0} requires filling in {1}.'.format( \
        self.params[reqname].title, self.params[paramname].title)] = 1
                
                    # check if required param is filled in but not the requiring
                    if self.params[paramname]:
                        if not self.params[reqname].store or \
                            not self.params[reqname].inputvalues:
                            self.params[paramname].warnings['Possible orphan field: field {0} is \
                            required by field {1}, but that has not been filled \
                            in.'.format(self.params[paramname].title,
                            self.params[reqname].title)] = 1

        # check if any error in any parameter of set
        for paramname in params_passed:
                if self.params[paramname].errors:
                    self.error = True
   
    def load_json_metadata(self):
        try:
            with open( os.path.join(self.tmpdir, 'metadata.json')) as fp:
                tmp_meta = json.load(fp)
        except IOError:
            tmp_meta = { 'metadata': {},
                'files': {fn : {} for fn in self.allfiles }}
        return tmp_meta
    
    def save_json(self, meta, location=None):
        if not location:
            dst = os.path.join(self.tmpdir, 'metadata.json')
        # else: verify existing dst? #FIXME
        with open( dst, 'w') as fp:
            json.dump(meta, fp)

    def autodetection(self):
        if self.is_outlier:
            files_to_detect = self.outlierfiles
        else:
            files_to_detect = self.allfiles
        outfiles = { fn : {} for fn in files_to_detect }
        for paramname in self.params:
            if self.params[paramname].autodetect_param:
                dep = self.params[paramname].depends_on
                outfiles = self.params[paramname].autodetect(outfiles,
                    self.params[dep].inputvalues)
        
        storedmeta = self.load_json_metadata()
        for fn in outfiles:
            for p in outfiles[fn]:
                storedmeta['files'][fn][p] = outfiles[fn][p]
        
        self.save_json(storedmeta)

    def save_tmp_parameters(self):
        ### store parameters, in either outlier or base form
        tmp_metadata = self.load_json_metadata()
        
        if self.is_outlier:
            # detect outlier differences with base
            to_store = {} 
            for paramname in self.params:
                new_vals = self.params[paramname].inputvalues
                stored = tmp_metadata['metadata'][paramname]
                if type(stored) != list:
                    stored = [stored]
                if sorted(stored) == sorted(new_vals):
                    continue
                if len(new_vals) == 1:
                    new_vals = new_vals[0]
                to_store[paramname] = new_vals
            
            for fn in self.outlierfiles:
                for p in to_store:
                    tmp_metadata['files'][fn][p] = to_store[p]

        else:
            # new base metadata. store
            params = {}
            for paramname in self.params:
                if self.params[paramname].store:
                    values = self.params[paramname].inputvalues
                    if len(values) == 1:
                        values = values[0]
                    params[paramname] = values
                else:
                    print paramname

            tmp_metadata['metadata'] = params
        
        self.save_json(tmp_metadata)

    def gather_metadata(self, user):
        # first update select fields values if necessary DEPRECATE?
        for p in self.params:
            if self.params[p].update_values:
                pass # FIXME

        self.metadata = self.load_json_metadata()
        
        # FIXME not concurrency safe, use database to store, then get nr from
        # there and store on server
        infofiles = glob.glob(os.path.join(consts.TMP_INFOFILE_DIR, '*.json'))
        infofiles.extend(glob.glob(os.path.join(consts.INFOFILE_LOCATION,
        '*.json')))
        if not infofiles:
            infofiles = ['info0.json']
        newfilenr = max([int(x.replace('info','').replace('.json', '')) for x in \
                infofiles]) + 1
        new_file = 'info{0}.json'.format(str(newfilenr))
        general_info = {
        'date':  datetime.date.strftime(datetime.datetime.now(), '%Y%m%d'),
        'mail': user.email,
        'status': 'new',
        'infofilename': new_file
        }
        self.metadata['general_info'] = general_info
        self.save_json(self.metadata)

    def push_definite_metadata(self, formdata):
        self.tmpdir = formdata['tmpdir']
        print self.tmpdir
        metadata = self.load_json_metadata()

        src = os.path.join(self.tmpdir, 'metadata.json')
        dst = os.path.join(consts.TMP_INFOFILE_DIR, metadata['general_info']['infofilename'])
        print os.listdir(self.tmpdir)
        print dst
        try:
            shutil.copy(src, dst)
        except OSError:
            print 'OOPsie'
            raise
