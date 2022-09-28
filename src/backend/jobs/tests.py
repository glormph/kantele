import os
from datetime import datetime
from django.test import TestCase, Client
from celery import states as cstates


from datasets import tests as dt
from rawstatus import models as rm
from datasets import models as dm
from jobs import models as jm
from kantele import settings


class BaseJobTest(dt.BaseDatasetTest):
    def setUp(self):
        super().setUp()
        self.job = jm.Job.objects.create(funcname=self.jobname,
                timestamp=datetime.now(), state='done', kwargs={})
        self.taskid = 'task_abc123'
        self.task = jm.Task.objects.create(job=self.job, asyncid=self.taskid, state='PROCESSING', args=[])


class TestRenamedProject(BaseJobTest):
    url = '/jobs/set/projectname/'
    jobname = 'rename_top_lvl_projectdir'
    p_newname = 'test_newp1'

    def setUp(self):
        super().setUp()
        kwargs={'proj_id': self.p1.pk, 'srcname': self.p1.name, 'newname': self.p_newname}
        self.job.kwargs = kwargs
        self.job.save()

    def test_wrong_client(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': settings.STORAGECLIENT_APIKEY + 'abc123'})
        self.assertEqual(resp.status_code, 403)
        resp = self.cl.post(self.url, content_type='application/json',
            data={'no_client_id': 1})
        self.assertEqual(resp.status_code, 403)

    def test_normal(self):
        producer = rm.Producer.objects.create(name='testprod', client_id='prod_abc123', shortname='tp')
        sftype = rm.StoredFileType.objects.create(name='test', filetype='tst')
        rf = rm.RawFile.objects.create(name='testrf', producer=producer,
            source_md5='abcdefgh', size=10, date=datetime.now(),
            claimed=True)
        dm.DatasetRawFile.objects.create(dataset=self.ds1, rawfile=rf)
        sf=rm.StoredFile.objects.create(rawfile=rf, filename=rf.name,
            servershare=self.ss, path=self.ds1.storage_loc, md5=rf.source_md5, checked=True,
            filetype=sftype)
        resp = self.cl.post(self.url, content_type='application/json', data={
            'client_id': settings.STORAGECLIENT_APIKEY, 'task': self.taskid,
            'proj_id': self.p1.pk, 'newname': self.p_newname,
            })
        self.assertEqual(resp.status_code, 200)
        newpath = os.path.join(self.p_newname, *self.ds1.storage_loc.split(os.path.sep)[1:])
        sf.refresh_from_db()
        self.ds1.refresh_from_db()
        self.assertEqual(self.ds1.storage_loc, newpath)
        self.assertEqual(sf.path, newpath)
        self.task.refresh_from_db()
        self.assertEqual(self.task.state, cstates.SUCCESS)


class TestUpdateStorageLocDset(BaseJobTest):
    url = '/jobs/set/dsstoragepath/'
    jobname = 'rename_dset_storage_loc'
    p_newname = 'test_newp1'

    def setUp(self):
        super().setUp()

    def test_wrong_client(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': settings.ANALYSISCLIENT_APIKEY})
        self.assertEqual(resp.status_code, 403)
        resp = self.cl.post(self.url, content_type='application/json',
            data={'no_client_id': 1})
        self.assertEqual(resp.status_code, 403)

    def test_dset_storupdate_ok(self):
        newstorloc = 'another/location'
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': settings.STORAGECLIENT_APIKEY,
                    'dset_id': self.ds1.pk, 'storage_loc': newstorloc,
                    'task' : self.task.asyncid})
        self.assertEqual(resp.status_code, 200)
        self.ds1.refresh_from_db()
        self.assertEqual(self.ds1.storage_loc, newstorloc)
        self.task.refresh_from_db()
        self.assertEqual(self.task.state, cstates.SUCCESS)
