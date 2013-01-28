import os, datetime
from pymongo.objectid import ObjectId
from models import Dataset
from parameters import ParameterSet
from db.dbaccess import DatabaseAccess

class MetadataSet(object):
    def __init__(self):
        self.is_new_dataset = False
        self.obj_id = False
        self.status = False
        self.more_outliers = False
        self.db = DatabaseAccess()
    
    def initialize_new_dataset(self, request):
        # FIXME what to do if the button is pressed twice? Create new or show
        # the old from session? probably create new.
        draft_oid = self.db.insert_draft_metadata( {} )
        request.session['draft_id'] = draft_oid 
        self.db.insert_draft_files({'draft_id': draft_oid})
        self.db.insert_draft_outliers({'draft_id': draft_oid})
        return str(draft_oid)
    
    def copy_dataset(self, request, oid_str):
        draft_oid = self.draft_from_fullmetadata('copy', oid_str)
        request.session['draft_id'] = draft_oid
        return str(draft_oid)

    def edit_dataset(self, request, oid_str):
        draft_oid = self.draft_from_fullmetadata('edit', oid_str)
        request.session['draft_id'] = draft_oid
        return str(draft_oid) 
    
    def show_dataset(self, request, oid_str):
        session_id = request.session.get('draft_id', None)
        files, basemd, outliers = self.load_from_db(ObjectId(oid_str), session_id)
        self.create_paramsets(request.user, files, basemd, outliers)
    
    def store_dataset(self, request, oid_str):
        sessionid = request.session.get('draft_id', None)
        curdate = datetime.date.strftime(datetime.datetime.now(), '%Y%m%d')
        
        if not sessionid == oid_str:
            pass # TODO ERROR
        files, basemd, outliers = self.load_from_db(ObjectId(oid_str),
                    sessionid)
        # remove draft_id, status=edit/copy, metadata_id, etc from data
        metadata_id = basemd.pop('metadata_id', None)
        for x in ['draft_id', 'status', '_id']: # TODO this should be solve elsewhere, what if we change...
            # ...a name somewhere!?
            files.pop(x, None)
            basemd.pop(x, None)
            for rec in outliers:
                rec.pop(x, None) # pops from the original dict data object, no
                                 # need to redefine and put in new list.
        
        # convert outliers to files in fullmeta
        files = files['files']
        for out in outliers:
            for key,val in out['metadata'].items():
                if key in basemd and val != basemd[key]:
                    for fn in out['files']:
                        files[fn][key] = val

        # parse extension from files since mongo doesnt accept '.' in its keys
        newfiles = {}
        for fn in files:
            newfn = os.path.splitext(fn)
            newfiles[newfn[0]] = files[fn]
            newfiles[newfn[0]]['extension'] = newfn[1]
        files = newfiles

        # get id from SQL DB that registers mongoid/users
        # Base infofilename on that. Concurrency problem solved.
        d = Dataset(user=request.user,mongoid=metadata_id,date=datetime.datetime.now(),
                project=basemd['Project'], experiment=basemd['Experiment'])
        d.save()

        fullmeta = {'metadata': basemd, 'files': files}
        fullmeta['general_info'] = {'date': curdate,
                                    'mail': request.user.email,
                                    'status': 'new',
                                    'nr': d.id
                                    }

        if metadata_id: # only when editing, no general info update
            self.db.update_metadata(metadata_id,
                    {'metadata':fullmeta['metadata']}, replace=True)
            self.db.update_metadata(metadata_id, {'files':fullmeta['files']},
                    replace=True)
        else:
            self.db.insert_metadata_record(fullmeta)

    def draft_from_fullmetadata(self, task, obj_id_str):
        obj_id = ObjectId(obj_id_str)
        # load md from db
        files, basemd, outliers = self.load_from_db(obj_id)

        # create draftmeta dict, add status = 'editing/copy'
        basemd['status'] = task
        if task == 'edit':
            basemd['metadata_id'] = self.fullmeta['_id']
        else:
            files, outliers = {}, [{}]

        draft_id = self.db.insert_draft_metadata(basemd)
        files['draft_id'] = draft_id
        self.db.insert_draft_files(files)
        for record in outliers:
            outliers['draft_id'] = draft_id
            self.db.insert_draft_outliers(record)

        return draft_id
            
    def load_from_db(self, obj_id, sessionid=None):
        self.fullmeta = self.db.get_metadata(obj_id)
        if not self.fullmeta:
            # data is either draft, or doesn't exist
            if sessionid == obj_id:
                pass # TODO error, NO ACCESS or redirect!
            else:
                basemetadata = self.db.get_metadata(obj_id, draft=True)
                if not basemetadata:
                    pass # NO ACCESS!, redirect

                else:
                    files = self.db.get_files(obj_id)
                    outliers = []
                    for record in self.db.get_outliers(obj_id):
                        outliers.append(record)
                     
        else:
            # We're either editing or we're just showing.
            basemetadata = self.fullmeta['metadata']
            files = {'files': self.fullmeta['files'].keys()}
            outliers = self.get_outliers_from_fullmetadata(self.fullmeta)
        
        return files, basemetadata, outliers
    
    def get_outliers_from_fullmetadata(self, md):
        outliers = []
        for fn in md['files']:
            if set(md['metadata']).intersection(md['files'][fn]):
                outlier = { x: md['metadata'][x] for x in md['metadata'] }
                for key in set(md['metadata']).intersection(md['files'][fn]):
                    outlier[key] = md['files'][fn][key]
                outliers.append(outlier)
            else:
                continue
        return outliers

    def create_paramsets(self, user, files, basemetadata, outliers):
        self.baseparamset = ParameterSet()
        self.baseparamset.initialize(user, basemetadata)
        self.outlierparamsets = []
        for record in outliers: 
            pset = ParameterSet()
            pset.initialize(user, record)
            self.outlierparamsets.append( pset )

    def incoming_form(self, req, obj_id_str):
        obj_id = ObjectId(obj_id_str)
        # validate session id with req.
        sessionid = req.session.get('draft_id', None)
        if not sessionid == obj_id:
            pass # NO ACCESS!
        
        formtgt = [x for x in req.POST if x.startswith('target_')][0]
        
        if formtgt == 'target_add_files':
            if not req.POST['pastefiles'] and \
                'selectfiles' not in req.POST:
                pass # TODO set error flag and redirect to file form
            else:
                filelist = req.POST['pastefiles']
                if filelist == '':
                    filelist = []
                else:
                    filelist = [x.strip() for x in filelist.strip().split('\n')]
                if 'selectfiles' in req.POST:
                    filelist.extend(req.POST.getlist('selectfiles'))
                self.db.insert_files({ 'files': filelist, 'draft_id': obj_id})

        # with obj_id, get tmp metadata['sessionid']
        # paramset, validate, store.
        elif formtgt in ['target_write_metadata','target_define_outliers',
                        'more_outliers']:
            self.paramset = ParameterSet()
            self.paramset.incoming_metadata(req.POST)

            if not self.paramset.error:
                self.paramset.do_autodetection()
                self.paramset.generate_metadata_for_db()
                if formtgt == 'target_write_metadata':
                    self.db.update_draft_metadata(obj_id,
                            self.paramset.metadata, replace=False)
                else:
                    outlierfiles = req.POST.get('outlierfiles', None)
                    # check outliers
                    if not outlierfiles:
                        pass # ERROR, no files specified
                    files, basemd, outliers = self.load_from_db(obj_id,
                            sessionid)
                    if self.paramset.metadata == basemd:
                        pass # ERROR, basemeta == outlier
                    
                    for outlier in outliers:
                        if self.paramset.metadata == outlier['metadata']:
                            pass # ERROR, outlier == previous outlier
                        elif set(outlierfiles).intersection(outlier['files']):
                            pass # ERROR

                    # Checks passed, save to db:
                    self.more_outliers = 'more_outliers'==formtgt
                    meta_for_db = { 'draft_id': obj_id, 
                                    'metadata': self.paramset.metadata,
                                    'files': outlierfiles }

                    self.db.insert_outliers(meta_for_db)

            else:
                pass
                # TODO check for errors, set flag and redirect target
        
    

    def get_uploaded_files(self):
        return sorted(os.listdir('/mnt/kalevalatmp'))

