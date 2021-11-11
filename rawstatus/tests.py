from datetime import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User

from kantele import settings
from rawstatus import models as rm
from analysis import models as am
from jobs import models as jm


class BaseFilesTest(TestCase):
    def setUp(self):
        self.clientid = 'abcde'
        self.notclientid = 'qwerty'
        self.cl = Client()
        self.ss = rm.ServerShare.objects.create(name=settings.TMPSHARENAME, uri='test.tmp', share='/home/testtmp')
        self.ft = rm.StoredFileType.objects.create(name='testft', filetype='tst')
        self.prod = rm.Producer.objects.create(name='prod1', client_id=self.clientid, shortname='p1')
        self.newraw = rm.RawFile.objects.create(name='file1', producer=self.prod, source_md5='abcde12345',
                size=100, date=datetime.now(), claimed=False)


class TransferStateTest(BaseFilesTest):
    url = '/files/transferstate/'

    def setUp(self):
        super().setUp()
        self.trfraw = rm.RawFile.objects.create(name='filetrf', producer=self.prod, source_md5='defghi123',
                size=100, date=datetime.now(), claimed=False)
        self.doneraw = rm.RawFile.objects.create(name='filedone', producer=self.prod, source_md5='jklmnop123',
                size=100, date=datetime.now(), claimed=False)
        self.multifileraw = rm.RawFile.objects.create(name='filemulti', producer=self.prod, source_md5='jsldjak8',
                size=100, date=datetime.now(), claimed=False)
        self.trfsf = rm.StoredFile.objects.create(rawfile=self.trfraw, filename=self.trfraw.name, servershare_id=self.ss.id,
                path='', md5=self.trfraw.source_md5, checked=False, filetype_id=self.ft.id)
        self.donesf = rm.StoredFile.objects.create(rawfile=self.doneraw, filename=self.doneraw.name, servershare_id=self.ss.id,
                path='', md5=self.doneraw.source_md5, checked=True, filetype_id=self.ft.id)
        self.multisf1 = rm.StoredFile.objects.create(rawfile=self.multifileraw, filename=self.multifileraw.name, servershare_id=self.ss.id,
                path='', md5=self.multifileraw.source_md5, checked=False, filetype_id=self.ft.id)
        ft2 = rm.StoredFileType.objects.create(name='testft2', filetype='tst')
        multisf2 = rm.StoredFile.objects.create(rawfile=self.multifileraw, filename=self.multifileraw.name, 
                servershare_id=self.ss.id, path='', md5='', checked=False, filetype_id=ft2.pk)

    def test_transferstate_done(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': self.clientid, 'fnid': self.doneraw.id})
        rj = resp.json()
        self.assertEqual(rj['transferstate'], 'done')

    def test_transferstate_scp(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': self.clientid, 'fnid': self.newraw.id})
        rj = resp.json()
        self.assertEqual(rj['transferstate'], 'transfer')

    def test_transferstate_wait(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': self.clientid, 'fnid': self.trfraw.id})
        rj = resp.json()
        self.assertEqual(rj['transferstate'], 'wait')
        job = jm.Job.objects.get()
        self.assertEqual(job.funcname, 'get_md5')
        self.assertEqual(job.kwargs, {'sf_id': self.trfsf.id, 'source_md5': 'defghi123'})

    def test_failing_transferstate(self):
        # test all the fail HTTPs
        resp = self.cl.get(self.url)
        self.assertEqual(resp.status_code, 405)
        resp = self.cl.post(self.url, content_type='application/json', data={'hello': 'test'})
        self.assertEqual(resp.status_code, 400)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': 'wrongid', 'fnid': 1})
        self.assertEqual(resp.status_code, 403)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': self.clientid, 'fnid': 99})
        self.assertEqual(resp.status_code, 404)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': self.notclientid, 'fnid': 1})
        self.assertEqual(resp.status_code, 403)
        # raw with multiple storedfiles -> conflict
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': self.clientid, 'fnid': self.multisf1.rawfile_id})
        self.assertEqual(resp.status_code, 409)


class TestFileTransferred(BaseFilesTest):
    url = '/files/transferred/'

    def test_fails(self):
        resp = self.cl.get(self.url)
        self.assertEqual(resp.status_code, 405)
        resp = self.cl.post(self.url, data={'hello': 'test'})
        self.assertEqual(resp.status_code, 400)
        resp = self.cl.post(self.url, data={'fn_id': self.newraw.pk, 'client_id': self.notclientid,
            'ftype_id': self.ft.pk, 'filename': self.newraw.name})
        self.assertEqual(resp.status_code, 403)
        resp = self.cl.post(self.url, data={'fn_id': self.newraw.pk + 1000, 'client_id': self.clientid,
            'ftype_id': self.ft.pk, 'filename': self.newraw.name})
        self.assertEqual(resp.status_code, 403)
        resp = self.cl.post(self.url, data={'fn_id': self.newraw.pk, 'client_id': self.clientid,
            'ftype_id': self.ft.pk + 1000, 'filename': self.newraw.name})
        self.assertEqual(resp.status_code, 400)
        
    def test_two_requests(self):
        # FIXME how to do this async for checking if get_or_create is correct?
        resp = self.cl.post(self.url, data={'fn_id': self.newraw.pk, 'filename': self.newraw.name,
            'client_id': self.clientid, 'ftype_id': self.ft.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(jm.Job.objects.count(), 1)
        sf = self.newraw.storedfile_set.get()
        jobs = jm.Job.objects.filter(funcname='get_md5', kwargs={'source_md5': self.newraw.source_md5,
            'sf_id': sf.pk})
        self.assertEqual(jobs.count(), 1)
        self.assertEqual(sf.md5, self.newraw.source_md5)
        resp2 = self.cl.post(self.url, data={'fn_id': self.newraw.pk, 'filename': self.newraw.name,
            'client_id': self.clientid, 'ftype_id': self.ft.pk})
        self.assertEqual(jm.Job.objects.count(), 2)
        self.assertEqual(jobs.all().count(), 2)


class TestArchiveFile(BaseFilesTest):
    url = '/files/archive/'

    def setUp(self):
        super().setUp()
        username='testuser'
        email = 'test@test.com'
        password='12345'
        self.user = User(username=username, email=email)
        self.user.set_password(password)
        self.user.save() 
        login = self.cl.login(username=username, password=password)
        self.sfile = rm.StoredFile.objects.create(rawfile=self.newraw, filename=self.newraw.name, servershare_id=self.ss.id,
                path='', md5=self.newraw.source_md5, checked=False, filetype_id=self.ft.id)

    def test_get(self):
        resp = self.cl.get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_wrong_params(self):
        resp = self.cl.post(self.url, content_type='application/json', data={'hello': 'test'})
        self.assertEqual(resp.status_code, 400)

    def test_wrong_id(self):
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': -1})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()['error'], 'File does not exist')

    def test_claimed_file(self):
        dset_raw = rm.RawFile.objects.create(name='dset_file', producer=self.prod, source_md5='kjlmnop1234',
                size=100, date=datetime.now(), claimed=True)
        sfile = rm.StoredFile.objects.create(rawfile=dset_raw, filename=dset_raw.name, servershare_id=self.ss.id,
                path='', md5=dset_raw.source_md5, checked=False, filetype_id=self.ft.id)
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': sfile.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('File is in a dataset', resp.json()['error'])

    def test_already_archived(self):
        rm.PDCBackedupFile.objects.create(success=True, storedfile=self.sfile, pdcpath='')
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': self.sfile.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()['error'], 'File is already archived')

    def test_deleted_file(self):
        sfile1 = rm.StoredFile.objects.create(rawfile=self.newraw, filename=self.newraw.name, servershare_id=self.ss.id,
                path='', md5='deletedmd5', checked=False, filetype_id=self.ft.id,
                deleted=True)
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': sfile1.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()['error'], 'File is currently marked as deleted, can not archive')
        # purged file to also test the check for it. Unrealistic to have it deleted but
        # not purged obviously
        sfile2 = rm.StoredFile.objects.create(rawfile=self.newraw, filename=self.newraw.name, 
                servershare_id=self.ss.id, path='', md5='deletedmd5_2', checked=False, 
                filetype_id=self.ft.id, deleted=False, purged=True)
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': sfile2.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()['error'], 'File is currently marked as deleted, can not archive')

    def test_mzmlfile(self):
        pset = am.ParameterSet.objects.create(name='')
        nfw = am.NextflowWorkflow.objects.create(description='', repo='')
        wfv = am.NextflowWfVersion.objects.create(update='', commit='', filename='', nfworkflow=nfw,
                paramset=pset, kanteleanalysis_version=1, nfversion='')
        pwiz = am.Proteowizard.objects.create(version_description='', container_version='', nf_version=wfv)
        am.MzmlFile.objects.create(sfile=self.sfile, pwiz=pwiz)
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': self.sfile.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('Derived mzML files are not archived', resp.json()['error'])

    def test_analysisfile(self):
        prod = rm.Producer.objects.create(name='analysisprod', client_id=settings.ANALYSISCLIENT_APIKEY, shortname='pana')
        ana_raw = rm.RawFile.objects.create(name='ana_file', producer=prod, source_md5='kjlmnop1234',
                size=100, date=datetime.now(), claimed=True)
        sfile = rm.StoredFile.objects.create(rawfile=ana_raw, filename=ana_raw.name, servershare_id=self.ss.id,
                path='', md5=ana_raw.source_md5, checked=False, filetype_id=self.ft.id)
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': sfile.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('Analysis result files are not archived', resp.json()['error'])

    def test_ok(self):
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': self.sfile.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'state': 'ok'})
