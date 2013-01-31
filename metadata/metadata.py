import os, datetime
from bson.objectid import ObjectId
from models import Dataset, DraftDataset
from parameterset import ParameterSet

class MetadataSet(object):
    def __init__(self):
        self.is_new_dataset = False
        self.obj_id = False
        self.more_outliers = False
    
    def new_dataset(self, request):
        draft_oid = self.db.insert_draft_metadata( {} )
        self.initialize_new_dataset(request, draft_oid)
        return str(draft_oid)
    
    def copy_dataset(self, request, oid_str):
        draft_oid = self.draft_from_fullmetadata('copy', oid_str)
        self.initialize_new_dataset(request, draft_oid)
        return str(draft_oid)

    def edit_dataset(self, request, oid_str):
        draft_oid = self.draft_from_fullmetadata('edit', oid_str)
        request.session['draft_id'] = draft_oid
        request.session['metadatastatus'] = 'edit' 
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

        fullmeta = {'metadata': basemd, 'files': files}
        fullmeta['general_info'] = {'date': curdate,
                                    'mail': request.user.email,
                                    'status': 'storing',
                                    }

        if metadata_id: # only when editing, no general info update
            self.db.update_metadata(metadata_id,
                        {'metadata':fullmeta['metadata']})
            self.db.update_metadata(metadata_id, {'files':fullmeta['files']})
        else:
            metadata_id = self.db.insert_metadata_record(fullmeta)
            # get id from SQL DB that registers mongoid/users
            # Base infofilename on that. Concurrency problem solved.
            d = self.save_to_sql_db(Dataset, user=request.user,
                    mongoid=str(metadata_id),date=datetime.datetime.now(),
                    project=basemd['Project'], experiment=basemd['Experiment'])
            fullmeta['general_info']['status'] = 'new'
            fullmeta['general_info']['nr'] = d.id
            self.db.update_metadata(metadata_id, fullmeta, replace=True)

    def incoming_form(self, req, obj_id_str):
        self.obj_id = ObjectId(obj_id_str)
        # validate session id with req.
        sessionid = req.session.get('draft_id', None)
        if not sessionid == self.obj_id:
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
                    filelist = [ x.strip() for x in filelist.strip().split('\n') ]
                if 'selectfiles' in req.POST:
                    filelist.extend(req.POST.getlist('selectfiles'))
                
                filelist = [ os.path.splitext(x) for x in filelist ]
                self.db.update_files( self.obj_id, { 'files': { k[0]: {'extension':\
                            k[1][1:]} for k in filelist }})

        # with obj_id, get tmp metadata['sessionid']
        # paramset, validate, store.
        elif formtgt in ['target_write_metadata','target_define_outliers',
                        'target_more_outliers']:
            self.paramset = ParameterSet()
            self.paramset.incoming_metadata(req.POST)

            if not self.paramset.error:
                self.paramset.generate_metadata_for_db()
                if formtgt == 'target_write_metadata':
                    files = self.db.get_files(self.obj_id)
                    files['files'], autodet_done = \
                    self.paramset.do_autodetection(files['files'],
                            [fn for fn in files['files']] )
                    
                    self.db.update_draft_metadata(self.obj_id,
                            self.paramset.metadata, replace=False)
                else:
                    outlierfiles = req.POST.get('outlierfiles', None)
                    # check outliers
                    if not outlierfiles:
                        pass # ERROR, no files specified
                    files, basemd, outliers = self.load_from_db(self.obj_id,
                            sessionid)
                    
                    if self.paramset.metadata == basemd:
                        pass # ERROR, basemeta == outlier
                    
                    for outlier in outliers:
                        if self.paramset.metadata == outlier['metadata']:
                            pass # ERROR, outlier == previous outlier
                        elif set(outlierfiles).intersection(outlier['files']):
                            pass # ERROR
                    
                    files['files'], autodet_done = \
                    self.paramset.do_autodetection(files['files'],outlierfiles)
                    # Checks passed, save to db:
                    self.more_outliers = 'more_outliers'==formtgt
                    meta_for_db = { 'draft_id': self.obj_id, 
                                    'metadata': self.paramset.metadata,
                                    'files': outlierfiles }

                    self.db.insert_outliers(meta_for_db)
                
                if autodet_done: # DB hit is expensive, check first
                    self.db.update_files(self.obj_id, files)
            
            else:
                pass
                # TODO check for errors, set flag and redirect target
        
    def initialize_new_dataset(self, request, draft_oid):
        self.save_to_sql_db(DraftDataset, user=request.user, 
                mongoid=str(draft_oid), date=datetime.datetime.now())
        request.session['draft_id'] = draft_oid 
        request.session['metadatastatus'] = 'new' 
        self.db.insert_files({'draft_id': draft_oid})

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
        self.db.insert_files(files)
        for record in outliers:
            outliers['draft_id'] = draft_id
            self.db.insert_outliers(record)

        return draft_id
            
    def load_from_db(self, obj_id, sessionid=None):
        self.fullmeta = self.db.get_metadata(obj_id)
        if not self.fullmeta:
            # data is either draft, or doesn't exist
            if sessionid != obj_id:
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
            
        # convert mongo's unicode to utf-8
        # my first recursive function! What a mindwarp.
        def convert_dicts_unicode_to_utf8(d):
            if isinstance(d, dict):
                return { convert_dicts_unicode_to_utf8(k): \
                    convert_dicts_unicode_to_utf8(v) for k,v in d.items() }
            elif isinstance(d, list):
                return [convert_dicts_unicode_to_utf8(x) for x in d]
            elif isinstance(d, unicode):
                return d.encode('utf-8')
            else:
                return d

        basemetadata = convert_dicts_unicode_to_utf8(basemetadata)
        files = convert_dicts_unicode_to_utf8(files)
        newoutliers = []
        for outlier in outliers:
            newoutliers.append(convert_dicts_unicode_to_utf8(outlier))
        
        return files, basemetadata, newoutliers
    
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

    def save_to_sql_db(self, model, **kwargs):
        record = model(**kwargs)
        record.save()
        return record

    def get_uploaded_files(self):
        return sorted(os.listdir('/tmp'))

