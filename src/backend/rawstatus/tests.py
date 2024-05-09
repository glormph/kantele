import os
import json
import shutil
import zipfile
from io import BytesIO
from datetime import timedelta, datetime
from tempfile import mkdtemp

from celery import states
from django.utils import timezone
from django.contrib.auth.models import User

from kantele import settings
from kantele.tests import BaseTest, ProcessJobTest, BaseIntegrationTest
from rawstatus import models as rm
from rawstatus import jobs as rjobs
from datasets import models as dm
from analysis import models as am
from analysis import models as am
from jobs import models as jm
from jobs import jobs as jj


class BaseFilesTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.nottoken = 'blablabla'
        self.token= 'fghihj'
        self.uploadtoken = rm.UploadToken.objects.create(user=self.user, token=self.token,
                expires=timezone.now() + timedelta(1), expired=False,
                producer=self.prod, filetype=self.ft)
        # expired token
        rm.UploadToken.objects.create(user=self.user, token=self.nottoken, 
                expires=timezone.now() - timedelta(1), expired=False, 
                producer=self.prod, filetype=self.ft)

        self.registered_raw, _ = rm.RawFile.objects.get_or_create(name='file1', producer=self.prod,
                source_md5='b7d55c322fa09ecd8bea141082c5419d',
                size=100, date=timezone.now(), claimed=False)


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
        self.trfsf = rm.StoredFile.objects.create(rawfile=self.trfraw, filename=self.trfraw.name, servershare=self.sstmp,
                path='', md5=self.trfraw.source_md5, filetype=self.ft)
        self.donesf = rm.StoredFile.objects.create(rawfile=self.doneraw, filename=self.doneraw.name, servershare=self.sstmp,
                path='', md5=self.doneraw.source_md5, checked=True, filetype=self.ft)
        self.multisf1 = rm.StoredFile.objects.create(rawfile=self.multifileraw, filename=self.multifileraw.name, servershare=self.sstmp,
                path='', md5=self.multifileraw.source_md5, filetype=self.ft)
        # ft2 = rm.StoredFileType.objects.create(name='testft2', filetype='tst')
        # FIXME multisf with two diff filenames shouldnt be a problem right?
        multisf2 = rm.StoredFile.objects.create(rawfile=self.multifileraw,
                filename=f'{self.multifileraw.name}.mzML', 
                servershare=self.sstmp, path='', md5='', filetype=self.ft)

    def test_transferstate_done(self):
        sf = self.doneraw.storedfile_set.get()
        resp = self.cl.post(self.url, content_type='application/json',
                data={'token': self.token, 'fnid': self.doneraw.id})
        rj = resp.json()
        self.assertEqual(rj['transferstate'], 'done')
        pdcjobs = jm.Job.objects.filter(funcname='create_pdc_archive', kwargs={
            'sf_id': sf.pk, 'isdir': sf.filetype.is_folder})
        self.assertEqual(pdcjobs.count(), 1)

    def test_trfstate_done_libfile(self):
        '''Test if state done is correctly reported for uploaded library file,
        and that archiving and move jobs exist for it'''
        # Create lib file which is not claimed yet
        libraw = rm.RawFile.objects.create(name='another_libfiledone',
                producer=self.prod, source_md5='test_trfstate_libfile',
                size=100, claimed=False, date=timezone.now())
        sflib = rm.StoredFile.objects.create(rawfile=libraw, md5=libraw.source_md5,
                filetype=self.ft, checked=True, filename=libraw.name,
                    servershare=self.sstmp, path='')
        lf = am.LibraryFile.objects.create(sfile=sflib, description='This is a libfile')
        resp = self.cl.post(self.url, content_type='application/json',
                data={'token': self.token, 'fnid': libraw.id})
        rj = resp.json()
        self.assertEqual(rj['transferstate'], 'done')
        pdcjobs = jm.Job.objects.filter(funcname='create_pdc_archive', kwargs={
            'sf_id': sflib.pk, 'isdir': sflib.filetype.is_folder})
        self.assertEqual(pdcjobs.count(), 1)
        jobs = jm.Job.objects.filter(funcname='move_single_file', kwargs={'sf_id': sflib.pk,
            'dst_path': settings.LIBRARY_FILE_PATH,
            'newname': f'libfile_{lf.pk}_{sflib.filename}'})
        self.assertEqual(jobs.count(), 1)

    def test_trfstate_done_usrfile(self):
        '''Test if state done is correctly reported for uploaded userfile,
        and that archiving and move jobs exist for it'''
        # Create userfile during upload
        usrfraw, _ = rm.RawFile.objects.update_or_create(name='usrfiledone',
                producer=self.prod, source_md5='usrfmd5', size=100, 
                defaults={'claimed': True, 'date': timezone.now()})
        uft, _ = rm.StoredFileType.objects.get_or_create(name='ufileft', filetype='tst',
                is_rawdata=False)
        sfusr, _ = rm.StoredFile.objects.update_or_create(rawfile=usrfraw,
                md5=usrfraw.source_md5, filetype=uft,
                defaults={'filename': usrfraw.name, 'servershare': self.sstmp,
                    'path': '', 'checked': True})
        usedtoken, _ = rm.UploadToken.objects.update_or_create(user=self.user, token='usrffailtoken',
                expired=False, producer=self.prod, filetype=uft, defaults={
                    'expires': timezone.now() + timedelta(1)})
        userfile, _ = rm.UserFile.objects.get_or_create(sfile=sfusr,
                description='This is a userfile', upload=usedtoken)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'token': usedtoken.token, 'fnid': usrfraw.pk})
        rj = resp.json()
        self.assertEqual(rj['transferstate'], 'done')
        pdcjobs = jm.Job.objects.filter(funcname='create_pdc_archive', kwargs={
            'sf_id': sfusr.pk, 'isdir': sfusr.filetype.is_folder})
        self.assertEqual(pdcjobs.count(), 1)
        jobs = jm.Job.objects.filter(funcname='move_single_file', kwargs={'sf_id': sfusr.pk,
            'dst_path': settings.USERFILEDIR,
            'newname': f'userfile_{usrfraw.pk}_{sfusr.filename}'})
        self.assertEqual(jobs.count(), 1)

    def test_transferstate_transfer(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'token': self.token, 'fnid': self.registered_raw.id})
        rj = resp.json()
        self.assertEqual(rj['transferstate'], 'transfer')

    def test_transferstate_wait(self):
        upload_file = os.path.join(settings.TMP_UPLOADPATH,
                f'{self.trfraw.pk}.{self.trfsf.filetype.filetype}')
        jm.Job.objects.get_or_create(funcname='rsync_transfer', kwargs={
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

    def test_transfer_archive_only(self):
        # Check if file is deleted directly after upload with a purge job
        # TODO check if file goes to designated sensititve data storage from 
        # where it is archived and purged (non-accessible)
        uploadtoken = rm.UploadToken.objects.create(user=self.user, token='archiveonly',
                expires=timezone.now() + timedelta(1), expired=False,
                producer=self.prod, filetype=self.ft, archive_only=True)
        sf = self.doneraw.storedfile_set.get()
        resp = self.cl.post(self.url, content_type='application/json',
                data={'token': uploadtoken.token, 'fnid': sf.rawfile_id})
        jobs = jm.Job.objects.filter(funcname='purge_files', kwargs={'sf_ids': [sf.pk]})
        self.assertEqual(jobs.count(), 1)


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
        stddata = {'fn': self.registered_raw.name, 'token': False, 'size': 200,
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
        stddata = {'fn': self.registered_raw.name, 'token': self.token, 'size': 100,
                'date': datetime.timestamp(nowdate), 'md5': 'fake'}
        resp = self.cl.post(self.url, content_type='application/json',
                data=stddata)
        self.assertEqual(resp.status_code, 200)
        newraws = rm.RawFile.objects.filter(source_md5='fake', #date=nowdate,
                name=self.registered_raw.name, producer=self.prod, size=100) 
        self.assertEqual(newraws.count(), 1)
        self.assertTrue(nowdate - newraws.get().date < timedelta(seconds=60))

    def test_register_again(self):
        # create a rawfile
        self.test_normal() 
        # try one with same MD5, check if only one file is there
        nowdate = timezone.now()
        stddata = {'fn': self.registered_raw.name, 'token': self.token, 'size': 100,
                'date': datetime.timestamp(nowdate), 'md5': 'fake'}
        resp = self.cl.post(self.url, content_type='application/json',
                data=stddata)
        self.assertEqual(resp.status_code, 200)
        newraws = rm.RawFile.objects.filter(source_md5='fake',
                name=self.registered_raw.name, producer=self.prod, size=100) 
        self.assertEqual(newraws.count(), 1)
        self.assertEqual(resp.json()['state'], 'error')
        self.assertIn('is already registered', resp.json()['msg'])


class TestFileTransfer(BaseFilesTest):
    url = '/files/transfer/'

    def do_check_okfile(self, resp, infile_contents):
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'state': 'ok', 'fn_id': self.registered_raw.pk})
        sfns = rm.StoredFile.objects.filter(rawfile=self.registered_raw)
        self.assertEqual(sfns.count(), 1)
        sf = sfns.get()
        self.assertEqual(sf.md5, self.registered_raw.source_md5)
        self.assertFalse(sf.checked)
        upload_file = os.path.join(settings.TMP_UPLOADPATH,
                f'{self.registered_raw.pk}.{self.uploadtoken.filetype.filetype}')
        jobs = jm.Job.objects.filter(funcname='rsync_transfer', kwargs={
            'src_path': upload_file, 'sf_id': sf.pk})
        self.assertEqual(jobs.count(), 1)
        job = jobs.get()
        # this may fail occasionally
        self.assertTrue(sf.regdate + timedelta(milliseconds=10) > job.timestamp)
        upfile = f'{self.registered_raw.pk}.{sf.filetype.filetype}'
        with open(os.path.join(settings.TMP_UPLOADPATH, upfile)) as fp:
            self.assertEqual(fp.read(), infile_contents)

    def do_transfer_file(self, libdesc=False, userdesc=False, token=False, fname=False):
        # FIXME maybe break up, function getting overloaded
        '''Tries to upload file and checks if everything is OK'''
        fn = 'test_upload.txt'
        if not token:
            token = self.token
        if not fname:
            fname = self.registered_raw.name
        # FIXME rawstatus/ wrong place for uploads test files!
        with open(f'rawstatus/{fn}') as fp:
            stddata = {'fn_id': self.registered_raw.pk, 'token': token,
                    'filename': fname, 'file': fp}
            if libdesc:
                stddata['libdesc'] = libdesc
            elif userdesc:
                stddata['userdesc'] = userdesc
            resp = self.cl.post(self.url, data=stddata)
            fp.seek(0)
            uploaded_contents = fp.read()
        return resp, uploaded_contents

    def test_fails_badreq_badauth(self):
        # GET
        resp = self.cl.get(self.url)
        self.assertEqual(resp.status_code, 405)
        # No params
        resp = self.cl.post(self.url, data={'hello': 'test'})
        self.assertEqual(resp.status_code, 400)
        # Missing client ID /token (False)
        stddata = {'fn_id': self.registered_raw.pk, 'token': False,
                'libdesc': False, 'userdesc': False, 'filename': self.registered_raw.name}
        resp = self.cl.post(self.url, data=stddata)
        self.assertEqual(resp.status_code, 403)
        # Wrong token
        resp = self.cl.post(self.url, data= {**stddata, 'token': 'thisisnotatoken'})
        self.assertEqual(resp.status_code, 403)
        # Wrong fn_id
        resp = self.cl.post(self.url, 
                data={**stddata, 'fn_id': self.registered_raw.pk + 1000, 'token': self.token})
        self.assertEqual(resp.status_code, 403)
        # expired token
        resp = self.cl.post(self.url, data={**stddata, 'token': self.nottoken})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('invalid or expired', resp.json()['error'])
        
    def test_transfer_file(self):
        resp, upload_content = self.do_transfer_file()
        self.do_check_okfile(resp, upload_content)

    def test_transfer_again(self):
        '''Transfer already existing file, e.g. overwrites of previously
        found to be corrupt file'''
        # Create storedfile which is the existing file w same md5, to get 403:
        rm.StoredFile.objects.create(rawfile=self.registered_raw, filetype=self.ft,
                md5=self.registered_raw.source_md5, servershare=self.sstmp, path='',
                filename=self.registered_raw.name)
        resp, upload_content = self.do_transfer_file()
        self.assertEqual(resp.status_code, 403)
        try:
            self.assertEqual(resp.json(), {'error': 'This file is already in the system: '
            f'{self.registered_raw.name}, if you are re-uploading a previously '
            'deleted file, consider reactivating from backup, or contact admin'})
        except AssertionError:
            self.assertEqual(resp.json(), {'error': 'Another file in the system has the same name '
        f'and is stored in the same path ({settings.TMPSHARENAME} - {settings.TMPPATH}/{self.registered_raw.name}. '
        'Please investigate, possibly change the file name or location of this or the other '
        'file to enable transfer without overwriting.'})

    def test_transfer_same_name(self):
        # Test trying to upload file with same name/path but diff MD5
        other_raw = rm.RawFile.objects.create(name=self.registered_raw.name, producer=self.prod,
                source_md5='fake_existing_md5', size=100, date=timezone.now(), claimed=False)
        rm.StoredFile.objects.create(rawfile=other_raw, filetype=self.ft,
                md5=other_raw.source_md5, servershare=self.sstmp, path=settings.TMPPATH,
                filename=other_raw.name)
        resp, upload_content = self.do_transfer_file()
        self.assertEqual(resp.status_code, 403)
        try:
            self.assertEqual(resp.json(), {'error': 'This file is already in the system: '
            f'{self.registered_raw.name}, if you are re-uploading a previously '
            'deleted file, consider reactivating from backup, or contact admin'})
        except AssertionError:
            self.assertEqual(resp.json(), {'error': 'Another file in the system has the same name '
        f'and is stored in the same path ({settings.TMPSHARENAME} - {settings.TMPPATH}/{self.registered_raw.name}. '
        'Please investigate, possibly change the file name or location of this or the other '
        'file to enable transfer without overwriting.'})

    def test_transfer_file_namechanged(self):
        fname = 'newname'
        resp, content = self.do_transfer_file(fname=fname)
        self.do_check_okfile(resp, content)
        sf = rm.StoredFile.objects.get(rawfile=self.registered_raw)
        self.assertEqual(sf.filename, fname)
        self.registered_raw.refresh_from_db()
        self.assertEqual(self.registered_raw.name, fname)

    def test_libfile(self):
        self.uploadtoken = rm.UploadToken.objects.create(user=self.user, token='libfile',
                expires=timezone.now() + timedelta(1), expired=False,
                producer=self.prod, filetype=self.ft, is_library=True)
        resp, upload_content = self.do_transfer_file(libdesc='This is a libfile', token='libfile')
        self.do_check_okfile(resp, upload_content)
        libs = am.LibraryFile.objects.filter(sfile__rawfile=self.registered_raw, description='This is a libfile')
        self.assertEqual(libs.count(), 1)
    
    def test_userfile(self):
        token = 'userfile'
        self.uploadtoken = rm.UploadToken.objects.create(user=self.user, token=token,
                expires=timezone.now() + timedelta(1), expired=False,
                producer=self.prod, filetype=self.uft)
        resp, upload_content = self.do_transfer_file(userdesc='This is a userfile', token=token)
        self.do_check_okfile(resp, upload_content)
        ufiles = rm.UserFile.objects.filter(sfile__rawfile=self.registered_raw,
                description='This is a userfile', upload__token=token)
        self.assertEqual(ufiles.count(), 1)
        ufiles.delete()
    
    def test_userlib_fail(self):
        token = 'userfilefail'
        uploadtoken = rm.UploadToken.objects.create(user=self.user, token=token,
                expires=timezone.now() + timedelta(1), expired=False,
                producer=self.prod, filetype=self.uft)
        resp, upload_content = self.do_transfer_file(token=token)
        self.assertEqual(resp.status_code, 403)
        self.assertIn('User file needs a description', resp.json()['error'])

#        elif self.uploadtoken.is_library and not libdesc:
#            self.assertEqual(resp.status_code, 403)
#            self.assertIn('Library file needs a description', resp.json()['error'])


class TestArchiveFile(BaseFilesTest):
    url = '/files/archive/'

    def setUp(self):
        super().setUp()
        self.sfile = rm.StoredFile.objects.create(rawfile=self.registered_raw, filename=self.registered_raw.name, servershare_id=self.sstmp.id,
                path='', md5=self.registered_raw.source_md5, filetype_id=self.ft.id)

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
        resp = self.cl.post(self.url, content_type='application/json',
                data={'item_id': self.oldsf.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('File is in a dataset', resp.json()['error'])

    def test_already_archived(self):
        rm.PDCBackedupFile.objects.create(success=True, storedfile=self.sfile, pdcpath='')
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': self.sfile.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()['error'], 'File is already archived')

    def test_deleted_file(self):
        sfile1 = rm.StoredFile.objects.create(rawfile=self.registered_raw, filename=self.registered_raw.name, servershare_id=self.sstmp.id,
                path='', md5='deletedmd5', filetype_id=self.ft.id,
                deleted=True)
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': sfile1.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()['error'], 'File is currently marked as deleted, can not archive')
        # purged file to also test the check for it. Unrealistic to have it deleted but
        # not purged obviously, as jobrunner shouldnt trigger that - except for when there is a delete job
        # which is deleted before running (no post-job purge set), which is bad!
        sfile2 = rm.StoredFile.objects.create(rawfile=self.registered_raw,
                filename=f'{self.registered_raw.name}_purged', 
                servershare_id=self.sstmp.id, path='', md5='deletedmd5_2',
                filetype_id=self.ft.id, deleted=False, purged=True)
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': sfile2.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()['error'], 'File is currently marked as deleted, can not archive')

    def test_mzmlfile(self):
        am.MzmlFile.objects.create(sfile=self.sfile, pwiz=self.pwiz)
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': self.sfile.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('Derived mzML files are not archived', resp.json()['error'])

    def test_analysisfile(self):
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': self.anasfile.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('Analysis result files are not archived', resp.json()['error'])

    def test_ok(self):
        resp = self.cl.post(self.url, content_type='application/json', data={'item_id': self.sfile.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'state': 'ok'})


class TestDownloadUploadScripts(BaseFilesTest):
    url = '/files/datainflow/download/'
    zipsizes = {'kantele_upload.sh': 337,
            'kantele_upload.bat': 185,
            'upload.py': 26072,
            'transfer.bat': 177,
            'transfer_config.json': 202,
            'setup.bat': 689,
            }

    def setUp(self):
        super().setUp()
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

class TestPurgeFilesJob(ProcessJobTest):
    jobclass = rjobs.PurgeFiles

    def test_fns(self):
        kwargs = {'sf_ids': [self.f3sf.pk, self.oldsf.pk]}
        self.job.process(**kwargs)
        exp_t = [
                ((self.f3sf.servershare.name, os.path.join(self.f3sf.path, self.f3sf.filename),
                    self.f3sf.pk, self.f3sf.filetype.is_folder), {}),
                ((self.oldsf.servershare.name, os.path.join(self.oldsf.path, self.oldsf.filename),
                    self.oldsf.pk, self.oldsf.filetype.is_folder), {})
                ]
        self.check(exp_t)

    def test_is_dir(self):
        self.ft.is_folder = True
        self.ft.save()
        kwargs = {'sf_ids': [self.f3sf.pk, self.f3sfmz.pk]}
        self.job.process(**kwargs)
        exp_t = [
                ((self.f3sf.servershare.name, os.path.join(self.f3sf.path, self.f3sf.filename),
                    self.f3sf.pk, True), {}),
                ((self.f3sfmz.servershare.name, os.path.join(self.f3sfmz.path, self.f3sfmz.filename),
                    self.f3sfmz.pk, False), {})
                ]
        self.check(exp_t)


class TestMoveSingleFile(ProcessJobTest):
    jobclass = rjobs.MoveSingleFile

    def test_mv_fn(self):
        newpath = os.path.split(self.f3sf.path)[0]
        kwargs = {'sf_id': self.f3sf.pk, 'dst_path': newpath}
        self.assertEqual(self.job.check_error(**kwargs), False)
        self.job.process(**kwargs)
        exp_t = [((self.f3sf.filename, self.f3sf.servershare.name, self.f3sf.path, newpath,
            self.f3sf.pk, self.f3sf.servershare.name), {})]
        self.check(exp_t)

    def test_error_duplicatefn(self):
        # Another fn exists w same name
        oldraw = rm.RawFile.objects.create(name=self.f3sf.filename, producer=self.prod,
                source_md5='rename_oldraw_fakemd5', size=10, date=timezone.now(), claimed=True)
        sf = rm.StoredFile.objects.create(rawfile=oldraw, filename=self.f3sf.filename, md5=oldraw.source_md5,
                filetype=self.ft, servershare=self.f3sf.servershare, path='oldpath', checked=True)
        newpath = os.path.split(self.f3path)
        kwargs = {'sf_id': sf.pk, 'dst_path': self.f3sf.path}
        self.assertIn('A file in path', self.job.check_error(**kwargs))
        self.assertIn('already exists. Please choose another', self.job.check_error(**kwargs))

        # A dataset has the same name as the file
        run = dm.RunName.objects.create(name='run1.raw', experiment=self.exp1)
        storloc = os.path.join(self.p1.name, self.exp1.name, self.dtype.name, run.name)
        ds = dm.Dataset.objects.create(date=self.p1.registered, runname=run,
                datatype=self.dtype, storageshare=self.ssnewstore, storage_loc=storloc)
        newpath, newname = os.path.split(storloc)
        kwargs = {'sf_id': sf.pk, 'dst_path': newpath, 'newname': newname}
        self.assertIn('A dataset with the same directory name as your new', self.job.check_error(**kwargs))


class TestRenameFile(BaseIntegrationTest):
    url = '/files/rename/'

    def test_renamefile(self):
        # There is no mzML for this sfile:
        self.f3sfmz.delete()
        oldfn = self.f3sf.filename
        oldname, ext = os.path.splitext(oldfn)
        newname = f'renamed_{oldname}'
        newfile_path = os.path.join(self.f3path, f'{newname}{ext}')
        kwargs_postdata = {'sf_id': self.f3sf.pk, 'newname': newname}
        # First call HTTP
        resp = self.post_json(data=kwargs_postdata)
        self.assertEqual(resp.status_code, 200)
        file_path = os.path.join(self.f3path, self.f3sf.filename)
        self.assertTrue(os.path.exists(file_path))
        self.assertFalse(os.path.exists(newfile_path))
        self.f3sf.refresh_from_db()
        self.assertEqual(self.f3sf.filename, oldfn)
        job = jm.Job.objects.last()
        self.assertEqual(job.kwargs, kwargs_postdata)
        # Now run job
        self.run_job()
        job.refresh_from_db()
        self.assertEqual(job.state, jj.Jobstates.PROCESSING)
        self.assertFalse(os.path.exists(file_path))
        self.assertTrue(os.path.exists(newfile_path))

    def test_cannot_create_job(self):
        # Try with non-existing file
        resp = self.post_json(data={'sf_id': -1000, 'newname': self.f3sf.filename})
        self.assertEqual(resp.status_code, 403)
        rj = resp.json()
        self.assertEqual('File does not exist', rj['error'])

        # Create file record
        oldfn = 'rename_oldfn.raw'
        oldraw = rm.RawFile.objects.create(name=oldfn, producer=self.prod,
                source_md5='rename_oldraw_fakemd5', size=10, date=timezone.now(), claimed=True)
        sf = rm.StoredFile.objects.create(rawfile=oldraw, filename=oldfn, md5=oldraw.source_md5,
                filetype=self.ft, servershare=self.f3sf.servershare, path=self.f3sf.path, checked=True)
        # Try with no file ownership 
        resp = self.post_json(data={'sf_id': sf.pk, 'newname': self.f3sf.filename})
        self.assertEqual(resp.status_code, 403)
        rj = resp.json()
        self.assertEqual('Not authorized to rename this file', rj['error'])

        self.user.is_superuser = True
        self.user.save()

        # Try rename to existing file
        resp = self.post_json(data={'sf_id': sf.pk, 'newname': self.f3sf.filename})
        self.assertEqual(resp.status_code, 403)
        rj = resp.json()
        self.assertIn('A file in path', rj['error'])
        self.assertIn('already exists. Please choose', rj['error'])


class TestDeleteFile(BaseIntegrationTest):
    jobname = 'purge_files'

    def test_file(self):
        kwargs = {'sf_ids': [self.f3sf.pk]}
        file_path = os.path.join(self.f3path, self.f3sf.filename)
        self.assertTrue(os.path.exists(file_path))
        self.assertFalse(os.path.isdir(file_path))

        job = jm.Job.objects.create(funcname=self.jobname, kwargs=kwargs, timestamp=timezone.now(),
                state=jj.Jobstates.PENDING)
        self.run_job()
        task = job.task_set.get()
        self.assertEqual(task.state, states.SUCCESS)
        self.assertFalse(os.path.exists(file_path))
        self.f3sf.refresh_from_db()
        self.assertTrue(self.f3sf.deleted)
        self.assertTrue(self.f3sf.purged)

    def test_dir(self):
        self.f3sf.filename = self.run1.name
        self.f3sf.path = os.path.split(self.storloc)[0]
        self.f3sf.save()
        self.ft.is_folder = True
        self.ft.save()
        # storloc, a dir, is now the file
        file_path = os.path.join(settings.SHAREMAP[self.ssnewstore.name], self.storloc)
        self.assertTrue(os.path.exists(file_path))
        self.assertTrue(os.path.isdir(file_path))

        kwargs = {'sf_ids': [self.f3sf.pk]}
        job = jm.Job.objects.create(funcname=self.jobname, kwargs=kwargs, timestamp=timezone.now(),
                state=jj.Jobstates.PENDING)
        self.run_job()
        task = job.task_set.get()
        self.assertEqual(task.state, states.SUCCESS)
        self.assertFalse(os.path.exists(file_path))
        self.f3sf.refresh_from_db()
        self.assertTrue(self.f3sf.deleted)
        self.assertTrue(self.f3sf.purged)


    def test_no_file(self):
        '''Test without an actual file in a dir will not error, as it will register
        that it has already deleted this file.
        TODO Maybe we SHOULD error, as the file will be not there, so who knows where
        it is now?
        '''
        badfn = 'badraw'
        badraw = rm.RawFile.objects.create(name=badfn, producer=self.prod,
                source_md5='badraw_fakemd5', size=10, date=timezone.now(), claimed=True)
        badsf = rm.StoredFile.objects.create(rawfile=badraw, filename=badfn,
                    md5=badraw.source_md5, filetype=self.ft, servershare=self.ssnewstore,
                    path=self.storloc, checked=True)
        file_path = os.path.join(badsf.path, badsf.filename)
        self.assertFalse(os.path.exists(file_path))

        kwargs = {'sf_ids': [badsf.pk]}
        job = jm.Job.objects.create(funcname=self.jobname, kwargs=kwargs, timestamp=timezone.now(),
                state=jj.Jobstates.PENDING)
        self.run_job()
        self.assertEqual(job.task_set.get().state, states.SUCCESS)
        badsf.refresh_from_db()
        self.assertTrue(badsf.deleted)
        self.assertTrue(badsf.purged)

    def test_fail_expect_dir(self):
        self.ft.is_folder = True
        self.ft.save()
        kwargs = {'sf_ids': [self.f3sf.pk]}
        job = jm.Job.objects.create(funcname=self.jobname, kwargs=kwargs, timestamp=timezone.now(),
                state=jj.Jobstates.PENDING)
        self.run_job()
        task = job.task_set.get()
        self.assertEqual(task.state, states.FAILURE)
        path_noshare = os.path.join(self.f3sf.path, self.f3sf.filename)
        full_path = os.path.join(self.f3path, self.f3sf.filename)
        msg = (f'When trying to delete file {path_noshare}, expected a directory, but encountered '
                'a file')
        self.assertEqual(task.taskerror.message, msg)
        self.assertTrue(os.path.exists(full_path))
        self.f3sf.refresh_from_db()
        self.assertFalse(self.f3sf.deleted)
        self.assertFalse(self.f3sf.purged)

    def test_fail_expect_file(self):
        self.f3sf.filename = self.run1.name
        self.f3sf.path = os.path.split(self.storloc)[0]
        self.f3sf.save()
        file_path = os.path.join(self.f3path)
        self.assertTrue(os.path.exists(file_path))
        self.assertTrue(os.path.isdir(file_path))          

        kwargs = {'sf_ids': [self.f3sf.pk]}
        job = jm.Job.objects.create(funcname=self.jobname, kwargs=kwargs, timestamp=timezone.now(),
                state=jj.Jobstates.PENDING)
        self.run_job()
        task = job.task_set.get()
        self.assertEqual(task.state, states.FAILURE)
        path_noshare = os.path.join(self.f3sf.path, self.f3sf.filename)
        msg = (f'When trying to delete file {path_noshare}, expected a file, but encountered '
                'a directory')
        self.assertEqual(task.taskerror.message, msg)
        self.assertTrue(os.path.exists(file_path))
        self.f3sf.refresh_from_db()
        self.assertFalse(self.f3sf.deleted)
        self.assertFalse(self.f3sf.purged)


#class TestDeleteDataset(BaseIntegrationTest):
