import os
from pymongo.objectid import ObjectId
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
        request.session['draft_id'] = draft_oid # FIXME is this returned? Is the
        # session really chnaged?
        self.db.insert_draft_files({'draft_id': draft_oid})
        self.db.insert_draft_outliers({'draft_id': draft_oid})
        return str(draft_oid)
    
    def edit_dataset(self, request, oid_str):
        session_id = request.session.get('draft_id', None)
        self.load_from_db(session_id, ObjectId(oid_str) ) 
        #mds.update_db_status('tmp')
        #mds.create_draft_from_metadata()
    
    def show_dataset(self, request, oid):
        session_id = request.session.get('draft_id', None)
        files, basemd, outliers = self.load_from_db(session_id, ObjectId(oid))
        self.create_paramsets(request.user, files, basemd, outliers)

    def create_draft_from_existing_metadata(self):
        md = {self.fullmeta['metadata'][k] for k in self.fullmeta['metadata']}
        md['metadata_id'] = str(self.fullmeta['_id'])
        md['status'] = 'editing'
        
        files = {'files': self.fullmeta['files'][:], 
                'metadata_id': str(self.fullmeta['_id'])}
        
        # FIXME When multiple people concurrently edit the metadata, you can't just remove
        # need an id to bind to a session or something
        self.mongo.run('remove', 'draftmeta', {'metadata_id': md['metadata_id']})
        self.mongo.run('remove', 'files', {'metadata_id': md['metadata_id']})
        self.mongo.run('remove', 'outliers', {'metadata_id': md['metadata_id']})

        self.db.insert_draft_record('draftmeta', md)
        self.db.insert_draft_record('files', files)
        
        for outlier in self.fullmeta['outliers']:
            outlier['metadata_id'] = str(self.fullmeta['_id'])
            self.insert_draft_record('outliers', outlier)

    def load_from_db(self, sessionid, obj_id):
        self.fullmeta = self.db.get_metadata(obj_id)
        if not self.fullmeta:
            # data is either draft, or doesn't exist
            # check if session ID ok
            if sessionid == obj_id:
                pass # TODO error, NO ACCESS or redirect!
            # check if exist in draft
            else:
                basemetadata = self.db.get_metadata(obj_id, draft=True)
                if not basemetadata:
                    pass # NO ACCESS!, redirect

                else: # load also outliers and files
                    files = self.db.get_files(obj_id)
                    outliers = []
                    for record in self.db.get_outliers(obj_id):
                        self.outliers.append(record)
                     
        else:
            # We're either editing or we're just showing.
            self.basemetadata = self.fullmeta['metadata']
            # TODO extract outliers et al from fullmeta
        
        return files, basemetadata, outliers

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
                self.db.insert_files({ 'files': [x for x in filelist],
                            'draft_id': obj_id } ) 

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
                    # TODO check if we need to write more than just
                    # paramset.metadata here. _id stays the same even w/o $set
                    self.db.update_draft_metadata(obj_id,
                            self.paramset.metadata)
                else:
                    outlierfiles = req.POST.get('outlierfiles', None)
                    # check outliers
                    if not outlierfiles:
                        pass # ERROR, no files specified
                    files, basemd, outliers = self.load_from_db(sessionid, obj_id)
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

