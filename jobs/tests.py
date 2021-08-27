import os
from datetime import datetime
from django.test import TestCase, Client


from datasets import tests as dt
from rawstatus import models as rm
from datasets import models as dm
from jobs import models as jm
from kantele import settings


class TestRenamedProject(dt.BaseDatasetTest):
    url = '/jobs/set/projectname/'

    def setUp(self):
        super().setUp()

    def test_wrong_client(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': settings.STORAGECLIENT_APIKEY + 'abc123'})
        self.assertEqual(resp.status_code, 403)
        resp = self.cl.post(self.url, content_type='application/json',
            data={'no_client_id': 1})
        self.assertEqual(resp.status_code, 403)
        resp = self.cl.post(self.url, content_type='application/json',
            data={'client_id': settings.STORAGECLIENT_APIKEY, 
                'task': 'nonexistent',
                })
        self.assertEqual(resp.status_code, 403)

    def test_renamedproj(self):
        taskid = 'task_abc123'
        p_newname = 'test_newp1'
        producer = rm.Producer.objects.create(name='testprod', client_id='prod_abc123', shortname='tp')
        ss = rm.ServerShare.objects.create(name='testss', uri='t.t.t', share='/home/disk')
        sftype = rm.StoredFileType.objects.create(name='test', filetype='tst')
        job = jm.Job.objects.create(funcname='rename_top_lvl_projectdir',
                timestamp=datetime.now(),
                kwargs={'proj_id': self.p1.pk, 'srcname': self.p1.name,
                    'newname': p_newname}, state='done')
        task = jm.Task.objects.create(job=job, asyncid=taskid, state='DONE', args=[])
        rf = rm.RawFile.objects.create(name='testrf', producer=producer,
            source_md5='abcdefgh', size=10, date=datetime.now(),
            claimed=True)
        dm.DatasetRawFile.objects.create(dataset=self.ds1, rawfile=rf)
        leafpath = 'path/to/file'
        sf=rm.StoredFile.objects.create(rawfile=rf, filename=rf.name,
            servershare=ss, path=os.path.join('oldroot', leafpath), md5=rf.source_md5, checked=True,
            filetype=sftype)
        resp = self.cl.post(self.url, content_type='application/json', data={
            'client_id': settings.STORAGECLIENT_APIKEY,
            'task': taskid,
            })
        self.assertEqual(resp.status_code, 200)
        sf.refresh_from_db()
        self.assertEqual(sf.path, os.path.join(p_newname, leafpath))
