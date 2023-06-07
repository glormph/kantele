import os
from datetime import datetime
from django.utils import timezone
from django.test import TestCase, Client
from celery import states as cstates


from kantele.tests import BaseTest
from rawstatus import models as rm
from datasets import models as dm
from jobs import models as jm
from kantele import settings


class BaseJobTest(BaseTest):
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
        dm.DatasetRawFile.objects.create(dataset=self.ds, rawfile=rf)
        sf=rm.StoredFile.objects.create(rawfile=rf, filename=rf.name,
            servershare=self.ssnewstore, path=self.ds.storage_loc, md5=rf.source_md5, checked=True,
            filetype=sftype)
        resp = self.cl.post(self.url, content_type='application/json', data={
            'client_id': settings.STORAGECLIENT_APIKEY, 'task': self.taskid,
            'proj_id': self.p1.pk, 'newname': self.p_newname, 'sf_ids': [sf.pk]})
        self.assertEqual(resp.status_code, 200)
        newpath = os.path.join(self.p_newname, *self.ds.storage_loc.split(os.path.sep)[1:])
        sf.refresh_from_db()
        self.ds.refresh_from_db()
        self.assertEqual(self.ds.storage_loc, newpath)
        self.assertEqual(sf.path, newpath)
        self.task.refresh_from_db()
        self.assertEqual(self.task.state, cstates.SUCCESS)


class TestUpdateStorageLocDset(BaseJobTest):
    url = '/jobs/set/dsstoragepath/'
    jobname = 'rename_dset_storage_loc'

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
                    'dset_id': self.ds.pk, 'storage_loc': newstorloc,
                    'newsharename': False, 'task' : self.task.asyncid})
        self.assertEqual(resp.status_code, 200)
        self.ds.refresh_from_db()
        self.assertEqual(self.ds.storage_loc, newstorloc)
        self.task.refresh_from_db()
        self.assertEqual(self.task.state, cstates.SUCCESS)


class TestUpdateStorageLocFile(BaseJobTest):
    url = '/jobs/set/storagepath/'
    # multiple jobs use this, but take this job
    jobname = 'move_dset_servershare'

    def test_wrong_client(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': 'fake'})
        self.assertEqual(resp.status_code, 403)
        resp = self.cl.post(self.url, content_type='application/json',
            data={'no_client_id': 1})
        self.assertEqual(resp.status_code, 403)

    def test_one_fnid(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': settings.ANALYSISCLIENT_APIKEY, 'fn_id': self.oldsf.pk,
                    'dst_path': 'new_path', 'servershare': self.ssnewstore.name,
                    'task': self.taskid, 'newname': 'newfilename',
                    })
        self.assertEqual(resp.status_code, 200)
        self.oldsf.refresh_from_db()
        self.assertEqual(self.oldsf.path, 'new_path')
        self.assertEqual(self.oldsf.servershare, self.ssnewstore)
        self.assertEqual(self.oldsf.filename, 'newfilename')
        self.task.refresh_from_db()
        self.assertEqual(self.task.state, 'SUCCESS')
         
    def test_multifiles(self):
        raw2 = rm.RawFile.objects.create(name='file2', producer=self.prod,
                source_md5='r328j9dqhj32qh98ddh3982q',
                size=100, date=timezone.now(), claimed=False)
        sf2 = rm.StoredFile.objects.create(rawfile=raw2, filename=raw2.name, servershare=self.ssnewstore,
                path='', md5=raw2.source_md5, filetype=self.ft)
        newshare = rm.ServerShare.objects.create(name='newshare', server=self.newfserver, share='/')
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': settings.ANALYSISCLIENT_APIKEY, 'fn_ids': [self.oldsf.pk, sf2.pk],
                    'dst_path': 'new_path', 'servershare': newshare.name, 'task': self.taskid,
                    'newname': 'newfilename',
                    })
        self.assertEqual(resp.status_code, 200)
        self.oldsf.refresh_from_db()
        self.assertEqual(self.oldsf.path, 'new_path')
        self.assertEqual(self.oldsf.servershare, newshare)
        sf2.refresh_from_db()
        self.assertEqual(sf2.path, 'new_path')
        self.assertEqual(sf2.servershare, newshare)
        self.task.refresh_from_db()
        self.assertEqual(self.task.state, 'SUCCESS')
