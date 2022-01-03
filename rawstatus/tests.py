from datetime import timedelta
from django.utils import timezone
from django.test import TestCase, Client
from django.contrib.auth.models import User

from kantele import settings
from rawstatus import models as rm
from analysis import models as am
from analysis import models as am
from jobs import models as jm


class BaseFilesTest(TestCase):
    def setUp(self):
        self.nottoken = 'blablabla'
        self.token= 'fghihj'
        self.cl = Client()
        self.ss = rm.ServerShare.objects.create(name=settings.TMPSHARENAME, uri='test.tmp', share='/home/testtmp')
        self.ft = rm.StoredFileType.objects.create(name='testft', filetype='tst')
        self.prod = rm.Producer.objects.create(name='prod1', client_id='abcdefg', shortname='p1')
        self.newraw = rm.RawFile.objects.create(name='file1', producer=self.prod, source_md5='abcde12345',
                size=100, date=timezone.now(), claimed=False)
        self.username='testuser'
        email = 'test@test.com'
        self.password='12345'
        self.user = User(username=self.username, email=email)
        self.user.set_password(self.password)
        self.user.save() 
        rm.UploadToken.objects.create(user=self.user, token=self.token,
                expires=timezone.now() + timedelta(1), expired=False,
                producer=self.prod, filetype=self.ft)
        # expired token
        rm.UploadToken.objects.create(user=self.user, token=self.nottoken, 
                expires=timezone.now() - timedelta(1), expired=False, 
                producer=self.prod, filetype=self.ft)


class TransferStateTest(BaseFilesTest):
    url = '/files/transferstate/'

    def setUp(self):
        super().setUp()
        self.trfraw = rm.RawFile.objects.create(name='filetrf', producer=self.prod, source_md5='defghi123',
                size=100, date=timezone.now(), claimed=False)
        self.doneraw = rm.RawFile.objects.create(name='filedone', producer=self.prod, source_md5='jklmnop123',
                size=100, date=timezone.now(), claimed=False)
        self.multifileraw = rm.RawFile.objects.create(name='filemulti', producer=self.prod, source_md5='jsldjak8',
                size=100, date=timezone.now(), claimed=False)
        self.trfsf = rm.StoredFile.objects.create(rawfile=self.trfraw, filename=self.trfraw.name, servershare=self.ss,
                path='', md5=self.trfraw.source_md5, checked=False, filetype=self.ft)
        self.donesf = rm.StoredFile.objects.create(rawfile=self.doneraw, filename=self.doneraw.name, servershare=self.ss,
                path='', md5=self.doneraw.source_md5, checked=True, filetype=self.ft)
        self.multisf1 = rm.StoredFile.objects.create(rawfile=self.multifileraw, filename=self.multifileraw.name, servershare=self.ss,
                path='', md5=self.multifileraw.source_md5, checked=False, filetype=self.ft)
        # ft2 = rm.StoredFileType.objects.create(name='testft2', filetype='tst')
        # FIXME multisf with two diff filenames shouldnt be a problem right?
        multisf2 = rm.StoredFile.objects.create(rawfile=self.multifileraw, filename=self.multifileraw.name, 
                servershare=self.ss, path='', md5='', checked=False, filetype=self.ft)

    def test_transferstate_done(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'token': self.token, 'fnid': self.doneraw.id})
        rj = resp.json()
        self.assertEqual(rj['transferstate'], 'done')

    def test_transferstate_scp(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'token': self.token, 'fnid': self.newraw.id})
        rj = resp.json()
        self.assertEqual(rj['transferstate'], 'transfer')

    def test_transferstate_wait(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'token': self.token, 'fnid': self.trfraw.id})
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
                data={'token': 'wrongid', 'fnid': 1})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('invalid or expired', resp.json()['error'])
        resp = self.cl.post(self.url, content_type='application/json',
                data={'token': self.token, 'fnid': 99})
        self.assertEqual(resp.status_code, 404)
        # token expired
        resp = self.cl.post(self.url, content_type='application/json',
                data={'token': self.nottoken, 'fnid': 1})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('invalid or expired', resp.json()['error'])
        # wrong producer
        prod2 = rm.Producer.objects.create(name='prod2', client_id='secondproducer', shortname='p2')
        p2raw = rm.RawFile.objects.create(name='p2file1', producer=prod2, source_md5='p2rawmd5',
                size=100, date=timezone.now(), claimed=False)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'token': self.token, 'fnid': p2raw.id})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('is not from producer', resp.json()['error'])
        # raw with multiple storedfiles -> conflict
        resp = self.cl.post(self.url, content_type='application/json',
                data={'token': self.token, 'fnid': self.multisf1.rawfile_id})
        self.assertEqual(resp.status_code, 409)
        self.assertIn('there are multiple', resp.json()['error'])


class TestFileRegistered(BaseFilesTest):
    pass


class TestFileTransferred(BaseFilesTest):
    url = '/files/transferred/'

    def test_fails_badreq_badauth(self):
        # GET
        resp = self.cl.get(self.url)
        self.assertEqual(resp.status_code, 405)
        # No params
        resp = self.cl.post(self.url, content_type='application/json',
                data={'hello': 'test'})
        self.assertEqual(resp.status_code, 400)
        # Missing client ID /token (False)
        stddata = {'fn_id': self.newraw.pk, 'token': False,
                'libdesc': False, 'userdesc': False}
        resp = self.cl.post(self.url, content_type='application/json',
                data=stddata)
        self.assertEqual(resp.status_code, 403)
        # Wrong token
        resp = self.cl.post(self.url, content_type='application/json',
                data= {**stddata, 'token': self.nottoken})
        self.assertEqual(resp.status_code, 403)
        # Wrong fn_id
        resp = self.cl.post(self.url, content_type='application/json',
                data={**stddata, 'fn_id': self.newraw.pk + 1000, 'token': self.token})
        self.assertEqual(resp.status_code, 403)
        # expired token
        resp = self.cl.post(self.url, content_type='application/json',
                data={**stddata, 'token': self.nottoken})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('invalid or expired', resp.json()['error'])
        
    def test_transferred(self, existing_file=False, libdesc=False, userdesc=False):
        stddata = {'fn_id': self.newraw.pk, 'token': self.token,
                'libdesc': libdesc, 'userdesc': userdesc}
        resp = self.cl.post(self.url, content_type='application/json',
                data=stddata)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'state': 'ok', 'fn_id': self.newraw.pk})
        sfns = rm.StoredFile.objects.filter(rawfile=self.newraw)
        self.assertEqual(sfns.count(), 1)
        sf = sfns.get()
        self.assertEqual(sf.md5, self.newraw.source_md5)
        self.assertFalse(sf.checked)
        jobs = jm.Job.objects.filter(funcname='get_md5', kwargs={
            'source_md5': self.newraw.source_md5, 'sf_id': sf.pk})
        self.assertEqual(jobs.count(), 1)
        job = jobs.get()
        # this may fail occasionally
        timediff = 200 if existing_file else 10
        self.assertTrue(sf.regdate + timedelta(milliseconds=timediff) > job.timestamp)

    def test_transferred_again(self):
        '''Transfer already existing file, e.g. overwrites of previously
        found to be corrupt file'''
        rm.StoredFile.objects.create(rawfile=self.newraw, filetype=self.ft,
                md5=self.newraw.source_md5, servershare=self.ss, path='',
                filename=self.newraw.name, checked=False)
        self.test_transferred(existing_file=True)

    def test_libfile(self):
        self.test_transferred(libdesc='This is a libfile')
        libs = am.LibraryFile.objects.filter(sfile__rawfile=self.newraw, description='This is a libfile')
        self.assertEqual(libs.count(), 1)
    
    def test_userfile(self):
        self.test_transferred(userdesc='This is a userfile')
        ufiles = rm.UserFile.objects.filter(sfile__rawfile=self.newraw,
                description='This is a userfile', upload__token=self.token)
        self.assertEqual(ufiles.count(), 1)
    


class TestArchiveFile(BaseFilesTest):
    url = '/files/archive/'

    def setUp(self):
        super().setUp()
        login = self.cl.login(username=self.username, password=self.password)
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
                size=100, date=timezone.now(), claimed=True)
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
                size=100, date=timezone.now(), claimed=True)
        sfile = rm.StoredFile.objects.create(rawfile=ana_raw, filename=ana_raw.name, servershare_id=self.ss.id,
                path='', md5=ana_raw.source_md5, checked=False, filetype_id=self.ft.id)
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': sfile.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('Analysis result files are not archived', resp.json()['error'])

    def test_ok(self):
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': self.sfile.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'state': 'ok'})
