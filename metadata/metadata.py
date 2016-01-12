import datetime
from bson.objectid import ObjectId
from django.contrib.auth.models import User
from models import Dataset, DraftDataset, DatasetOwner
from parameterset import ParameterSet
from files import Files
from util import util
import metadataconfig


class MetadataSet(object):
    def __init__(self):
        self.is_new_dataset = False
        self.obj_id = False
        self.error = False
        self.config = metadataconfig.MetadataConfig()
        self.paramconf = ParameterSet()

    def new_dataset(self, request):
        userparams = self.paramconf.get_user_params()
        userparams = [up.name for up in userparams]
        user = '{0} {1}'.format(request.user.first_name.encode('utf-8'),
                                request.user.last_name.encode('utf-8'))
        draft_oid = self.db.insert_draft_metadata({up: user for up
                                                   in userparams})
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
        files, basemd = self.load_from_db(ObjectId(oid_str),
                                                    session_id)
        self.check_completed_stages(basemd, files, request.session)
        self.create_paramsets(request.user, files, basemd)
        self.paramset = self.baseparamset

    def show_errored_dataset(self, request, oid_str):
        session_id = request.session.get('draft_id', None)
        files, basemd = self.load_from_db(ObjectId(oid_str),
                                                    session_id)
        self.check_completed_stages(basemd, files, request.session)
        self.create_paramsets(request.user, files, basemd)

    def store_dataset(self, request, oid_str):
        """ SHould be turned into class later for diff storage forms"""
        sessionid = request.session.get('draft_id', None)
        curdate = datetime.date.strftime(datetime.datetime.now(), '%Y%m%d')

        if not sessionid == oid_str:
            pass  # TODO ERROR
        filesset, basemd = self.load_from_db(ObjectId(oid_str),
                                                       sessionid)
        # remove draft_id, status=edit/copy, metadata_id, etc from data
        metadata_id = basemd.pop('metadata_id', None)
        for x in ['draft_id', 'status', '_id']:
        # TODO this should be solved elsewhere, what if we change a name?
            filesset.pop(x, None)
            basemd.pop(x, None)
        fullmeta = {'metadata': basemd, 'files': filesset['files']}
        fullmeta['general_info'] = {'date': curdate,
                                    'mail': request.user.email,
                                    'status': 'storing',
                                    }

        if metadata_id:  # only when editing, no general info update
            self.db.update_metadata(metadata_id,
                                    {'metadata':fullmeta['metadata']})
            self.db.update_metadata(metadata_id, {'files': fullmeta['files']})
        else:
            metadata_id = self.db.insert_metadata_record(fullmeta)
            # get id from SQL DB that registers mongoid/users
            # Base infofilename on that. Concurrency problem solved.
            d = self.save_to_sql_db(Dataset, user=request.user,
                                    mongoid=str(metadata_id),
                                    date=datetime.datetime.now(),
                                    project=basemd['Project'],
                                    experiment=basemd['Experiment'])

            # map get dataset owners from base parameters and save to django db
            # FIXME this whole routine should be refactored!
            self.create_paramsets(request.user, filesset, basemd)
            owners = {x: 0 for x in self.baseparamset.return_dataset_owners()}
            for u in User.objects.all():
                name = '{0} {1}'.format(u.first_name.encode('utf-8'),
                                        u.last_name.encode('utf-8'))
                if name in owners:
                    owners[name] = u
            if request.user not in owners.values():
                owners['loggedin_user'] = request.user
            for o in owners.values():
                self.save_to_sql_db(DatasetOwner, dataset=d, owner=o)

            # save the whole metadata to mongo
            fullmeta['general_info']['status'] = 'new'
            fullmeta['general_info']['nr'] = d.id
            self.db.update_metadata(metadata_id, fullmeta, replace=True)

    def incoming_form(self, req, obj_id_str):
        # FIXME another routine on the refactoring list!
        self.obj_id = ObjectId(obj_id_str)
        # validate session id with req.
        sessionid = req.session.get('draft_id', None)
        if not sessionid == self.obj_id:
            self.mark_error('home', 'You have no access to the requested '
                            'resource. Perhaps the session has timed out?')

        formtgt = [x for x in req.POST if x.startswith('target_')][0]

        if formtgt == 'target_add_files':
            if not req.POST['pastefiles'] and 'selectfiles' not in req.POST:
                self.mark_error('return_to_form',
                                'You have not selected files')
                return
            else:
                files = Files()
                files.post_files(req.POST)
                if not files.check_file_formatting():
                    self.mark_error('return_to_form', 'Your files contain the'
                                    ' following forbidden characters: '
                                    '{0}'.format(
                                        ' '.join(files.forbidden_found)))

                self.db.update_files(self.obj_id,
                                     {'files': {k[0]: {'extension': k[1]}
                                                for k in files.filelist}})
        # with obj_id, get tmp metadata['sessionid']
        # paramset, validate, store.
        elif formtgt == 'target_write_metadata':
            files, basemd = self.load_from_db(self.obj_id, sessionid)
            self.paramset = ParameterSet()
            self.paramset.incoming_metadata(req.POST)
            if not self.paramset.error:
                # FIXME why next line? arent files already read above?
                files = self.db.get_files(self.obj_id)
                files['files'], autodet_done = \
                    self.paramset.do_autodetection(files['files'],
                                                   [fn for fn in
                                                    files['files']])
                self.paramset.parameter_lookup()
                self.paramset.generate_metadata_for_db()
                self.db.update_draft_metadata(self.obj_id,
                                              self.paramset.metadata,
                                              replace=False)
                if autodet_done:  # DB hit is expensive, check first
                    self.db.update_files(self.obj_id, files)
            else:
                self.mark_error('return_to_form', 'Errors in entered metadata')

    def mark_error(self, redirect, message):
        self.error = {'redirect': redirect, 'message': message}

    def initialize_new_dataset(self, request, draft_oid):
        self.save_to_sql_db(DraftDataset, user=request.user,
                            mongoid=str(draft_oid),
                            date=datetime.datetime.now())
        request.session['draft_id'] = draft_oid
        request.session['metadatastatus'] = 'new'
        self.db.insert_files({'draft_id': draft_oid})

    def draft_from_fullmetadata(self, task, obj_id_str):
        obj_id = ObjectId(obj_id_str)
        # load md from db
        files, basemd = self.load_from_db(obj_id)
        # create draftmeta dict, add status = 'editing/copy'
        basemd['status'] = task
        if task == 'edit':
            basemd['metadata_id'] = self.fullmeta['_id']
        draft_id = self.db.insert_draft_metadata(basemd)
        return draft_id

    def load_from_db(self, obj_id, sessionid=None):
        self.fullmeta = self.db.get_metadata(obj_id)
        if not self.fullmeta:
            # data is either draft, or doesn't exist
            if sessionid != obj_id:
                pass  # TODO error, NO ACCESS or redirect!
            else:
                basemetadata = self.db.get_metadata(obj_id, draft=True)
                if not basemetadata:
                    pass  # NO ACCESS!, redirect
                else:
                    files = self.db.get_files(obj_id)

        else:
            # We're either editing or we're just showing.
            basemetadata = self.fullmeta['metadata']
            files = {'files': self.fullmeta['files']}

        basemetadata = util.convert_dicts_unicode_to_utf8(basemetadata)
        files = util.convert_dicts_unicode_to_utf8(files)
        return files, basemetadata

    def create_paramsets(self, user, files, basemetadata):
        self.fileset = Files()
        self.fileset.load_files(files)
        self.baseparamset = ParameterSet()
        self.baseparamset.initialize(user, basemetadata)

    def save_to_sql_db(self, model, **kwargs):
        record = model(**kwargs)
        record.save()
        return record

    def check_completed_stages(self, basemd, files, session):
        self.tocomplete = ['files', 'metadata', 'store']
        self.completed = []
        self.completetitles = {'files': 'Files', 'metadata': 'Base Metadata',
                               'store': 'Store Metadata'}
        if 'files' in files and session['metadatastatus'] == 'new':
            self.completed.append('files')
        userparams = [x.name for x in self.paramconf.get_user_params()]
        if set(basemd.keys()).difference(userparams) != set(['_id']):
            self.completed.append('metadata')
        if not False in [x in self.completed for x in ['metadata', 'files']]:
            self.completed.append('store')
