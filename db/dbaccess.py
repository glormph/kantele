import os
import mongo, consts

class DatabaseAccess(object):
    def __init__(self):
        self.mongo = mongo.MongoConnection(consts.DBNAME, 'draft')

    def get_metadata(self, obj_id, draft=False):
        if draft:
            return self.mongo.run('find_one', 'draftmeta', {'_id': obj_id} )
        else:
            return self.mongo.run('find_one', 'metadata', {'_id': obj_id} )
    
    def get_files(self, obj_id):
        return self.mongo.run('find_one', 'files', {'draft_id': obj_id})

    def get_outliers(self, obj_id):
        return self.mongo.run('find', 'outliers', {'draft_id': obj_id})
    
    def insert_metadata_record(self, record):
        return self.mongo.run('insert', 'metadata', record)
    
    def insert_draft_metadata(self, bson):
        return self.insert_draft_record('draftmeta', bson)

    def insert_files(self, bson):
        return self.insert_draft_record('files', bson)

    def insert_outliers(self, bson):
        return self.insert_draft_record('outliers', bson)

    def insert_draft_record(self, coll, record):
        if coll in self.mongo.returnColnames()['draft']:
            return self.mongo.run('insert', coll, record)
        elif self.mongo.returnColnames()['draft'] == []:
            return self.mongo.run('insert', coll, record)
        else:
            raise ValueError, 'No {0} collection in draft db'.format(coll)
    
    def update_metadata(self, oid, record, replace=False):
        self.update_record('metadata', {'_id': oid}, record, replace)
    
    def update_files(self, oid, record, replace=False):
        self.update_record('files', {'draft_id': oid}, record, replace)
    
    def update_draft_metadata(self, oid, record, replace=False):
        self.update_record('draftmeta', {'_id': oid}, record, replace)
    
    def update_record(self, coll, spec, record, replace=False):
        if replace:
            self.mongo.run('update', coll, in_bson=spec, value_bson=record)
        else:
            self.mongo.run('update', coll, in_bson=spec, value_bson={'$set': \
                    record} )
            
    def upsert_draft_record(self, coll, spec, record):
        if coll != 'metadata':
                return self.mongo.run('upsert', coll, key_bson=spec, value_bson=record, ups=True)
        else:
            raise ValueError, 'No metadata collection in draft db'

    def get_rawfile_processed_status(self, fn):
        fname = os.path.splitext(fn)[0]
        dbrec = self.mongo.run('find_one', 'metadata',
            {'files.{0}'.format(fname):{'$exists': True},
            'general_info.status': 'new'},
            in_fields=['files.{0}.extension'.format(fname)])
        if dbrec:
            fullfn = fname + dbrec['files'][fname]['extension']
            if fullfn == fn:
                return True

        return False




