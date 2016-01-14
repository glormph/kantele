from pymongo import MongoClient
import consts


class MongoConnection(object):
    def __init__(self, meta, draft=None):
        try:
            self.con = MongoClient(host=consts.DBHOST)
        except:
            raise

        self.meta = self.con[meta]
        if draft:
            self.draft = self.con[draft]

        self.collmap = {
                'metadata'  :   self.meta.metadata,
                'draftmeta' :   self.draft.metadata,
                'files'     :   self.draft.files,
                }

        self.actionmap = {
        'insert'    :   self.ins,
        'update'    :   self.upd,
        'remove'    :   self.rem,
        'find'      :   self.fnd,
        'find_one'  :   self.fnd_one
        }


    def returnColnames(self):
        return {'metadata': 'metadata',
                'draft': [x for x in self.collmap.keys() if x != 'metadata']}

    def run(self, action, coll, in_bson=None, **kwargs):
        try:
            rval = self.actionmap[action](self.collmap[coll], in_bson, **kwargs)
            if rval:
                return rval
        except:
            print('MongoDB error caught while processing input action={0}, \
coll={1}, in_bson={2}'.format(action, coll, in_bson))

    def ins(self, coll, bson_obj):
        return coll.insert(bson_obj)

    def upd(self, coll, key_bson, value_bson, ups=False):
        coll.update(key_bson, value_bson, upsert=ups)
        return False

    def rem(self, coll, bson_obj):
        coll.remove(bson_obj)
        return False

    def fnd(self, coll, bson_obj, in_fields=None):
        if in_fields:
            return coll.find(bson_obj, fields=in_fields)
        else:
            return coll.find(bson_obj)

    def fnd_one(self, coll, bson_obj, in_fields=None):
        return coll.find_one(bson_obj, fields=in_fields)

