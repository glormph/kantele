import os
import json
import shutil
import zipfile
from io import BytesIO
from datetime import timedelta, datetime
from tempfile import mkdtemp

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
        self.fserver = rm.FileServer.objects.create(name='server1', uri='s1.test')
        self.ss = rm.ServerShare.objects.create(name=settings.TMPSHARENAME, server=self.fserver, share='/home/testtmp')
        self.ft = rm.StoredFileType.objects.create(name='testft', filetype='tst', is_rawdata=True)
        self.uft = rm.StoredFileType.objects.create(name='ufileft', filetype='tst', is_rawdata=False)
        self.prod = rm.Producer.objects.create(name='prod1', client_id='abcdefg', shortname='p1')
        msit = rm.MSInstrumentType.objects.create(name='test')
        rm.MSInstrument.objects.create(producer=self.prod, instrumenttype=msit, filetype=self.ft)
        self.newraw = rm.RawFile.objects.create(name='file1', producer=self.prod,
                source_md5='b7d55c322fa09ecd8bea141082c5419d',
                size=100, date=timezone.now(), claimed=False)
        self.username='testuser'
        email = 'test@test.com'
        self.password='12345'
        self.user = User(username=self.username, email=email)
        self.user.set_password(self.password)
        self.user.save() 
        self.uploadtoken = rm.UploadToken.objects.create(user=self.user, token=self.token,
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

    def test_transferstate_done(self, token=False):
        if not token:
            token = self.token
        resp = self.cl.post(self.url, content_type='application/json',
                data={'token': token, 'fnid': self.doneraw.id})
        rj = resp.json()
        self.assertEqual(rj['transferstate'], 'done')
        sf = self.doneraw.storedfile_set.get()
        pdcjobs = jm.Job.objects.filter(funcname='create_pdc_archive', kwargs={
            'sf_id': sf.pk, 'isdir': sf.filetype.is_folder})
        self.assertEqual(pdcjobs.count(), 1)

    def test_trfstate_done_lib_usrfile(self):
        self.doneraw = rm.RawFile.objects.create(name='libfiledone', producer=self.prod, source_md5='libfilemd5',
                size=100, date=timezone.now(), claimed=False)

        sflib = rm.StoredFile.objects.create(rawfile=self.doneraw, filename=self.doneraw.name,
                servershare=self.ss, path='', md5=self.doneraw.source_md5, checked=True,
                filetype=self.ft)
        lf = am.LibraryFile.objects.create(sfile=sflib, description='This is a libfile')
        self.test_transferstate_done()
        jobs = jm.Job.objects.filter(funcname='move_single_file', kwargs={'sf_id': sflib.pk,
            'dst_path': settings.LIBRARY_FILE_PATH,
            'newname': f'libfile_{lf.pk}_{sflib.filename}'})
        self.assertEqual(jobs.count(), 1)

        self.doneraw = rm.RawFile.objects.create(name='usrfiledone', producer=self.prod, source_md5='usrfmd5',
                size=100, date=timezone.now(), claimed=False)

        sfusr = rm.StoredFile.objects.create(rawfile=self.doneraw, filename=self.doneraw.name,
                servershare=self.ss, path='', md5=self.doneraw.source_md5, checked=True,
                filetype=self.uft)
        uf = rm.UserFile.objects.create(sfile=sfusr,
                description='This is a userfile', upload=self.uploadtoken)
        self.uploadtoken = rm.UploadToken.objects.create(user=self.user, token='usrffailtoken',
                expires=timezone.now() + timedelta(1), expired=False,
                producer=self.prod, filetype=self.uft)
        self.test_transferstate_done(self.uploadtoken.token)
        jobs = jm.Job.objects.filter(funcname='move_single_file', kwargs={'sf_id': sfusr.pk,
            'dst_path': settings.USERFILEDIR, 'newname': f'userfile_{self.doneraw.pk}_{sfusr.filename}'})
        self.assertEqual(jobs.count(), 1)

    def test_transferstate_transfer(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'token': self.token, 'fnid': self.newraw.id})
        rj = resp.json()
        self.assertEqual(rj['transferstate'], 'transfer')

    def test_transferstate_wait(self):
        upload_file = os.path.join(settings.TMP_UPLOADPATH,
                f'{self.trfraw.pk}.{self.trfsf.filetype.filetype}')
        jm.Job.objects.create(funcname='rsync_transfer', kwargs={
            'sf_id': self.trfsf.pk, 'src_path': upload_file,
            'dst_sharename': settings.TMPSHARENAME}, timestamp=timezone.now())
        resp = self.cl.post(self.url, content_type='application/json',
                data={'token': self.token, 'fnid': self.trfraw.id})
        rj = resp.json()
        self.assertEqual(rj['transferstate'], 'wait')
        # TODO test for no-rsync-job exists (wait but talk to admin)

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
    url = '/files/register/'

    def test_auth_etc_fails(self):
        # GET
        resp = self.cl.get(self.url)
        self.assertEqual(resp.status_code, 405)
        # No params
        resp = self.cl.post(self.url, content_type='application/json',
                data={'hello': 'test'})
        self.assertEqual(resp.status_code, 400)
        # Missing client ID /token (False)
        stddata = {'fn': self.newraw.name, 'token': False, 'size': 200,
                'date': 'fake', 'md5': 'fake'}
        resp = self.cl.post(self.url, content_type='application/json',
                data=stddata)
        self.assertEqual(resp.status_code, 403)
        # Wrong token
        resp = self.cl.post(self.url, content_type='application/json',
                data= {**stddata, 'token': self.nottoken})
        self.assertEqual(resp.status_code, 403)
        # expired token
        resp = self.cl.post(self.url, content_type='application/json',
                data={**stddata, 'token': self.nottoken})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('invalid or expired', resp.json()['error'])
        # Wrong date
        resp = self.cl.post(self.url, content_type='application/json',
                data={**stddata, 'token': self.token})
        self.assertEqual(resp.status_code, 400)

    def test_normal(self):
        nowdate = timezone.now()
        stddata = {'fn': self.newraw.name, 'token': self.token, 'size': 100,
                'date': datetime.timestamp(nowdate), 'md5': 'fake'}
        resp = self.cl.post(self.url, content_type='application/json',
                data=stddata)
        self.assertEqual(resp.status_code, 200)
        newraws = rm.RawFile.objects.filter(source_md5='fake', #date=nowdate,
                name=self.newraw.name, producer=self.prod, size=100) 
        self.assertEqual(newraws.count(), 1)
        self.assertTrue(nowdate - newraws.get().date < timedelta(seconds=60))

    def test_register_again(self):
        # create a rawfile
        self.test_normal() 
        # try one with same MD5, check if only one file is there
        nowdate = timezone.now()
        stddata = {'fn': self.newraw.name, 'token': self.token, 'size': 100,
                'date': datetime.timestamp(nowdate), 'md5': 'fake'}
        resp = self.cl.post(self.url, content_type='application/json',
                data=stddata)
        self.assertEqual(resp.status_code, 200)
        newraws = rm.RawFile.objects.filter(source_md5='fake',
                name=self.newraw.name, producer=self.prod, size=100) 
        self.assertEqual(newraws.count(), 1)
        self.assertEqual(resp.json()['state'], 'error')
        self.assertIn('is already registered', resp.json()['msg'])


class TestFileTransfer(BaseFilesTest):
    url = '/files/transfer/'

    def test_fails_badreq_badauth(self):
        # GET
        resp = self.cl.get(self.url)
        self.assertEqual(resp.status_code, 405)
        # No params
        resp = self.cl.post(self.url, data={'hello': 'test'})
        self.assertEqual(resp.status_code, 400)
        # Missing client ID /token (False)
        stddata = {'fn_id': self.newraw.pk, 'token': False,
                'libdesc': False, 'userdesc': False, 'filename': self.newraw.name}
        resp = self.cl.post(self.url, data=stddata)
        self.assertEqual(resp.status_code, 403)
        # Wrong token
        resp = self.cl.post(self.url, data= {**stddata, 'token': 'thisisnotatoken'})
        self.assertEqual(resp.status_code, 403)
        # Wrong fn_id
        resp = self.cl.post(self.url, 
                data={**stddata, 'fn_id': self.newraw.pk + 1000, 'token': self.token})
        self.assertEqual(resp.status_code, 403)
        # expired token
        resp = self.cl.post(self.url, data={**stddata, 'token': self.nottoken})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('invalid or expired', resp.json()['error'])
        
    def test_transfer_file(self, existing_file=False, libdesc=False, userdesc=False, token=False):
        '''Tries to upload file and checks if everything is OK'''
        fn = 'test_upload.txt'
        if not token:
            token = self.token
        with open(f'rawstatus/{fn}') as fp:
            stddata = {'fn_id': self.newraw.pk, 'token': token,
                    'filename': self.newraw.name, 'file': fp}
            if libdesc:
                stddata['libdesc'] = libdesc
            elif userdesc:
                stddata['userdesc'] = userdesc
            resp = self.cl.post(self.url, data=stddata)
            fp.seek(0)
            infile_contents = fp.read()
        # Now do checks
        if existing_file:
            self.assertEqual(resp.status_code, 403)
            self.assertEqual(resp.json(), {'error': 'This file is already in the system: '
            f'{self.newraw.name}, if you are re-uploading a previously '
            'deleted file, consider reactivating from backup, or contact admin'})
        elif not self.uploadtoken.filetype.is_rawdata and not userdesc:
            self.assertEqual(resp.status_code, 403)
            self.assertIn('User file needs a description', resp.json()['error'])
        elif self.uploadtoken.is_library and not libdesc:
            self.assertEqual(resp.status_code, 403)
            self.assertIn('Library file needs a description', resp.json()['error'])
        else:
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json(), {'state': 'ok', 'fn_id': self.newraw.pk})
            sfns = rm.StoredFile.objects.filter(rawfile=self.newraw)
            self.assertEqual(sfns.count(), 1)
            sf = sfns.get()
            self.assertEqual(sf.md5, self.newraw.source_md5)
            self.assertFalse(sf.checked)
            upload_file = os.path.join(settings.TMP_UPLOADPATH,
                    f'{self.newraw.pk}.{self.uploadtoken.filetype.filetype}')
            jobs = jm.Job.objects.filter(funcname='rsync_transfer', kwargs={
                'src_path': upload_file, 'sf_id': sf.pk})
            self.assertEqual(jobs.count(), 1)
            job = jobs.get()
            # this may fail occasionally
            self.assertTrue(sf.regdate + timedelta(milliseconds=10) > job.timestamp)
            upfile = f'{self.newraw.pk}.{sf.filetype.filetype}'
            with open(os.path.join(settings.TMP_UPLOADPATH, upfile)) as fp:
                self.assertEqual(fp.read(), infile_contents)

    def test_transfer_again(self):
        '''Transfer already existing file, e.g. overwrites of previously
        found to be corrupt file'''
        rm.StoredFile.objects.create(rawfile=self.newraw, filetype=self.ft,
                md5=self.newraw.source_md5, servershare=self.ss, path='',
                filename=self.newraw.name, checked=False)
        self.test_transfer_file(existing_file=True)

    def transfer_archive_only(self):
        self.uploadtoken = rm.UploadToken.objects.create(user=self.user, token='archiveonly',
                expires=timezone.now() + timedelta(1), expired=False,
                producer=self.prod, filetype=self.ft, archive_only=True)
        self.test_transfer_file(token='archiveonly')
        sf = rm.StoredFile.objects.get(rawfile=self.newraw)
        jobs = jm.Job.objects.filter(funcname='purge_files', kwargs={'sf_ids': [sf.pk]})
        self.assertEqual(jobs.count(), 1)

    def test_libfile(self):
        self.uploadtoken = rm.UploadToken.objects.create(user=self.user, token='libfile',
                expires=timezone.now() + timedelta(1), expired=False,
                producer=self.prod, filetype=self.ft, is_library=True)
        self.test_transfer_file(libdesc='This is a libfile', token='libfile')
        libs = am.LibraryFile.objects.filter(sfile__rawfile=self.newraw, description='This is a libfile')
        self.assertEqual(libs.count(), 1)
    
    def test_userfile(self):
        token = 'userfile'
        self.uploadtoken = rm.UploadToken.objects.create(user=self.user, token=token,
                expires=timezone.now() + timedelta(1), expired=False,
                producer=self.prod, filetype=self.uft)
        self.test_transfer_file(userdesc='This is a userfile', token=token)
        ufiles = rm.UserFile.objects.filter(sfile__rawfile=self.newraw,
                description='This is a userfile', upload__token=token)
        self.assertEqual(ufiles.count(), 1)
    
    def test_userlib_fail(self):
        token = 'userfilefail'
        self.uploadtoken = rm.UploadToken.objects.create(user=self.user, token=token,
                expires=timezone.now() + timedelta(1), expired=False,
                producer=self.prod, filetype=self.uft)
        self.test_transfer_file(token=token)


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


class TestDownloadUploadScripts(BaseFilesTest):
    url = '/files/datainflow/download/'
    zipsizes = {'kantele_upload.sh': 306,
            'kantele_upload.bat': 297,
            'upload.py': 24854,
            'transfer.bat': 177,
            'transfer_config.json': 202,
            'setup.bat': 689,
            }

    def setUp(self):
        super().setUp()
        login = self.cl.login(username=self.username, password=self.password)
        self.tmpdir = mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_fails_badreq_badauth(self):
        postresp = self.cl.post(self.url)
        self.assertEqual(postresp.status_code, 405)
        clientresp = self.cl.get(self.url, data={'client': 'none'})
        self.assertEqual(clientresp.status_code, 403)
        nowinresp = self.cl.get(self.url, data={'client': 'user'})
        self.assertEqual(nowinresp.status_code, 400)
        badwinresp = self.cl.get(self.url, data={'client': 'user', 'windows': 'yes'})
        self.assertEqual(badwinresp.status_code, 400)
        badinsnoprod = self.cl.get(self.url, data={'client': 'instrument'})
        self.assertEqual(badinsnoprod.status_code, 403)
        badinsbadprod = self.cl.get(self.url, data={'client': 'instrument', 'prod_id': 1000})
        self.assertEqual(badinsbadprod.status_code, 403)
        badinsbaddisk = self.cl.get(self.url, data={'client': 'instrument', 'prod_id': 1})
        self.assertEqual(badinsbaddisk.status_code, 403)

    def test_user_linuxmacos(self):
        resp = self.cl.get(self.url, data={'client': 'user', 'windows': '0'})
        self.assertEqual(resp.status_code, 200)
        with zipfile.ZipFile(BytesIO(b''.join(resp.streaming_content))) as zipfn:
            contents = zipfn.infolist()
            names = zipfn.namelist()
        # check if both files of correct name/size are there
        self.assertEqual(len(contents), 2)
        self.assertIn('kantele_upload.sh', names)
        self.assertIn('upload.py', names)
        for fn in contents:
            self.assertEqual(fn.file_size, self.zipsizes[fn.filename])

    def test_user_windows(self):
        resp = self.cl.get(self.url, data={'client': 'user', 'windows': '1'})
        self.assertEqual(resp.status_code, 200)
        with zipfile.ZipFile(BytesIO(b''.join(resp.streaming_content))) as zipfn:
            contents = zipfn.infolist()
            names = zipfn.namelist()
        # check if both files of correct name/size are there
        self.assertEqual(len(contents), 2)
        self.assertIn('kantele_upload.bat', names)
        self.assertIn('upload.py', names)
        for fn in contents:
            self.assertEqual(fn.file_size, self.zipsizes[fn.filename])

    def test_instrument(self):
        datadisk = 'D:'
        resp = self.cl.get(self.url, data={'client': 'instrument', 'prod_id': self.prod.pk,
            'datadisk': datadisk})
        self.assertEqual(resp.status_code, 200)
        with zipfile.ZipFile(BytesIO(b''.join(resp.streaming_content))) as zipfn:
            contents = {x.filename: x.file_size for x in zipfn.infolist()}
            names = zipfn.namelist()
            with zipfn.open('transfer_config.json') as tcfp:
                tfconfig = json.load(tcfp)
        self.assertEqual(len(names), 10)
        for fn in ['requests-2.28.1-py3-none-any.whl', 'certifi-2022.9.14-py3-none-any.whl', 
                'requests_toolbelt-0.9.1-py2.py3-none-any.whl', 'idna-3.4-py3-none-any.whl',
                'charset_normalizer-2.1.1-py3-none-any.whl', 'urllib3-1.26.12-py2.py3-none-any.whl'
                ]:
            self.assertIn(fn, names)
        for key,val in {'outbox': f'{datadisk}\outbox',
                'zipbox': f'{datadisk}\zipbox',
                'donebox': f'{datadisk}\donebox',
                'producerhostname': self.prod.name,
                'client_id': self.prod.client_id,
                'filetype_id': self.prod.msinstrument.filetype_id,
                'is_folder': 1 if self.prod.msinstrument.filetype.is_folder else 0,
                'host': settings.KANTELEHOST,
                'md5_stable_fns': self.prod.msinstrument.filetype.stablefiles,
                }.items():
            self.assertEqual(tfconfig[key], val)
        for fn in ['transfer.bat', 'upload.py', 'setup.bat']:
            self.assertEqual(contents[fn], self.zipsizes[fn])

# FIXME case for upload with archiving only
