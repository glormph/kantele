# Integration tests, including storage files etc
import os
import shutil
from time import sleep

from django.contrib.auth.models import User
from django.test import TestCase, LiveServerTestCase, Client
from django.utils import timezone
from django.core.management import call_command

from kantele import settings
from datasets import models as dm
from rawstatus import models as rm
from jobs import models as jm


class BaseTest(TestCase):
    '''Normal django tests inherit here'''

    def post_json(self, data):
        return self.cl.post(self.url, content_type='application/json', data=data)

    def setUp(self):
        # Clean directory containing storage servers
        for dirname in os.listdir('/storage'):
            if os.path.isdir(os.path.join('/storage', dirname)):
                shutil.rmtree(os.path.join('/storage', dirname))
        shutil.copytree('/fixtures', '/storage', dirs_exist_ok=True)
        self.cl = Client()
        username='testuser'
        email = 'test@test.com'
        password='12345'
        self.user = User(username=username, email=email)
        self.user.set_password(password)
        self.user.save() 
        login = self.cl.login(username=username, password=password)
        # storage backend
        self.newfserver = rm.FileServer.objects.create(name='server1', uri='s1.test')
        self.sstmp = rm.ServerShare.objects.create(name=settings.TMPSHARENAME, server=self.newfserver,
                share='/home/testtmp')
        self.ssnewstore = rm.ServerShare.objects.create(name=settings.PRIMARY_STORAGESHARENAME,
                server=self.newfserver, share='/home/storage')
        self.oldfserver = rm.FileServer.objects.create(name='oldserver', uri='s0.test')
        self.ssoldstorage = rm.ServerShare.objects.create(name=settings.STORAGESHARENAMES[0],
                server=self.oldfserver, share='/home/storage')

        # Datasets/projects prep
        dscomp, _ = dm.DatasetComponent.objects.get_or_create(name='files')
        self.dtype, _ = dm.Datatype.objects.get_or_create(name='dtype1')
        self.dtcomp, _ = dm.DatatypeComponent.objects.get_or_create(datatype=self.dtype, component=dscomp)
        qdt, _ = dm.Datatype.objects.get_or_create(name='Quantitative proteomics')
        self.ptype, _ = dm.ProjectTypeName.objects.get_or_create(name='testpt')
        self.pi, _ = dm.PrincipalInvestigator.objects.get_or_create(name='testpi')

        # File prep, producers etc
        self.ft, _ = rm.StoredFileType.objects.get_or_create(name='testft', filetype='tst',
                is_rawdata=True)
        self.prod, _ = rm.Producer.objects.get_or_create(name='prod1', client_id='abcdefg', shortname='p1')
        msit, _ = rm.MSInstrumentType.objects.get_or_create(name='test')
        rm.MSInstrument.objects.get_or_create(producer=self.prod, instrumenttype=msit,
                filetype=self.ft)

        # Project/dset on new storage
        self.p1, _ = dm.Project.objects.get_or_create(name='p1', pi=self.pi)
        dm.ProjType.objects.get_or_create(project=self.p1, ptype=self.ptype)
        self.exp1, _ = dm.Experiment.objects.get_or_create(name='e1', project=self.p1)
        self.run1, _ = dm.RunName.objects.get_or_create(name='run1', experiment=self.exp1)
        self.storloc = os.path.join(self.p1.name, self.exp1.name, self.dtype.name, self.run1.name)
        self.ds, _ = dm.Dataset.objects.update_or_create(date=self.p1.registered, runname=self.run1,
                datatype=self.dtype, defaults={'storageshare': self.ssnewstore, 
                    'storage_loc': self.storloc})
        dm.DatasetComponentState.objects.get_or_create(dataset=self.ds,
                defaults={'state': 'OK', 'dtcomp': self.dtcomp})
        self.contact, _ = dm.ExternalDatasetContact.objects.get_or_create(dataset=self.ds,
                defaults={'email': 'contactname'})
        dm.DatasetOwner.objects.get_or_create(dataset=self.ds, user=self.user)
        self.f3path = os.path.join(settings.SHAREMAP[self.ssnewstore.name], self.storloc)
        fn3 = 'raw3'
        f3size = os.path.getsize(os.path.join(self.f3path, fn3))
        self.f3raw = rm.RawFile.objects.create(name=fn3, producer=self.prod,
                source_md5='f3_fakemd5',
                size=f3size, date=timezone.now(), claimed=True)
        self.f3dsr, _ = dm.DatasetRawFile.objects.get_or_create(dataset=self.ds, rawfile=self.f3raw)
        self.f3sf, _ = rm.StoredFile.objects.update_or_create(rawfile=self.f3raw, filename=fn3,
                    md5=self.f3raw.source_md5, filetype=self.ft,
                    defaults={'servershare': self.ssnewstore, 'path': self.storloc, 
                        'checked': True})
        qt, _ = dm.QuantType.objects.get_or_create(name='testqt', shortname='tqt')
        dm.QuantDataset.objects.get_or_create(dataset=self.ds, quanttype=qt)
        self.qch, _ = dm.QuantChannel.objects.get_or_create(name='thech')
        self.qtch, _ = dm.QuantTypeChannel.objects.get_or_create(quanttype=qt, channel=self.qch)


        # Project/dataset/files on old storage
        oldfn = 'raw1'
        self.oldp, _ = dm.Project.objects.get_or_create(name='oldp', pi=self.pi)
        dm.ProjType.objects.get_or_create(project=self.oldp, ptype=self.ptype)
        self.oldexp, _ = dm.Experiment.objects.get_or_create(name='olde', project=self.oldp)
        self.oldrun, _ = dm.RunName.objects.get_or_create(name='run1', experiment=self.oldexp)
        self.oldstorloc = os.path.join(self.oldp.name, self.oldexp.name, self.oldrun.name)
        self.oldds, _ = dm.Dataset.objects.update_or_create(date=self.oldp.registered,
                runname=self.oldrun, datatype=self.dtype, defaults={
                    'storageshare': self.ssoldstorage, 'storage_loc': self.oldstorloc})
        dm.QuantDataset.objects.get_or_create(dataset=self.oldds, quanttype=qt)
        dm.DatasetComponentState.objects.get_or_create(dataset=self.oldds, dtcomp=self.dtcomp,
                state='OK')
        self.contact, _ = dm.ExternalDatasetContact.objects.get_or_create(dataset=self.oldds,
                email='contactname')
        dm.DatasetOwner.objects.get_or_create(dataset=self.oldds, user=self.user)
        self.oldfpath = os.path.join(settings.SHAREMAP[self.ssoldstorage.name], self.oldstorloc)
        oldsize = os.path.getsize(os.path.join(self.oldfpath, oldfn))
        self.oldraw = rm.RawFile.objects.create(name=oldfn, producer=self.prod,
                source_md5='old_to_new_fakemd5',
                size=oldsize, date=timezone.now(), claimed=True)
        self.olddsr, _ = dm.DatasetRawFile.objects.get_or_create(dataset=self.oldds, rawfile=self.oldraw)
        self.oldsf, _ = rm.StoredFile.objects.update_or_create(rawfile=self.oldraw, filename=oldfn,
                    md5=self.oldraw.source_md5, filetype=self.ft,
                    defaults={'servershare': self.ssoldstorage, 'path': self.oldstorloc, 
                        'checked': True})

        # Tmp rawfile
        tmpfn = 'raw2'
        tmpfpathfn = os.path.join(settings.SHAREMAP[self.sstmp.name], tmpfn)
        tmpsize = os.path.getsize(tmpfpathfn)
        self.tmpraw, _ = rm.RawFile.objects.get_or_create(name=tmpfn, producer=self.prod,
                source_md5='tmpraw_fakemd5',
                size=tmpsize, date=timezone.now(), claimed=False)
        self.tmpsf, _ = rm.StoredFile.objects.update_or_create(rawfile=self.tmpraw,
                md5=self.tmpraw.source_md5, defaults={'filename': tmpfn, 'servershare': self.sstmp,
                    'path': '', 'checked': True, 'filetype': self.ft})

        # Analysis files
        self.anaprod = rm.Producer.objects.create(name='analysisprod', client_id=settings.ANALYSISCLIENT_APIKEY, shortname='pana')
        self.ana_raw = rm.RawFile.objects.create(name='ana_file', producer=self.anaprod, source_md5='kjlmnop1234',
                size=100, date=timezone.now(), claimed=True)
        self.anasfile = rm.StoredFile.objects.create(rawfile=self.ana_raw, filename=self.ana_raw.name,
                servershare_id=self.sstmp.id, path='', md5=self.ana_raw.source_md5,
                filetype_id=self.ft.id)


class BaseIntegrationTest(LiveServerTestCase):
    # use a live server so that jobrunner can interface with it (otherwise only dummy
    # test client can do that)
    port = 80
    host = '0.0.0.0'

    def setUp(self):
        BaseTest.setUp(self)

    def post_json(self, data):
        return self.cl.post(self.url, content_type='application/json', data=data)


class TestMultiStorageServers(BaseIntegrationTest):

    def test_add_newtmp_files_to_old_dset(self):
        # Fresh start in case multiple tests
        url = '/datasets/save/files/'
        postdata = {'dataset_id': self.oldds.pk, 'added_files': {'fn2': {'id': self.tmpraw.pk}}, 'removed_files': {}}
        resp = self.cl.post(url, content_type='application/json', data=postdata)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(os.path.exists(self.oldfpath))
        newdsr = dm.DatasetRawFile.objects.filter(dataset=self.oldds, rawfile=self.tmpraw)
        self.assertEqual(newdsr.count(), 1)
        self.tmpraw.refresh_from_db()
        self.assertTrue(self.tmpraw.claimed)
        # call job runner to run rsync
        call_command('runjobs')
        sleep(3)
        self.assertFalse(os.path.exists(self.oldfpath))
        newdspath = os.path.join(settings.SHAREMAP[self.ssnewstore.name], self.oldstorloc)
        self.assertTrue(os.path.exists(os.path.join(newdspath, self.oldsf.filename)))
        self.oldsf.refresh_from_db()
        self.assertEqual(self.oldsf.servershare_id, self.ssnewstore.pk)
        self.oldds.refresh_from_db()
        self.assertEqual(self.oldds.storageshare_id, self.ssnewstore.pk)
        # Check if move file tmp to newstorage has waited for the rsync job
        self.assertFalse(os.path.exists(os.path.join(newdspath, self.tmpsf.filename)))
        self.tmpsf.refresh_from_db()
        self.assertEqual(self.tmpsf.path, '')
        self.assertEqual(self.tmpsf.servershare_id, self.sstmp.pk)
        # Now execute move file job
        call_command('runjobs') # first mark prev job as DONE
        call_command('runjobs')
        sleep(3)
        self.assertTrue(os.path.exists(os.path.join(newdspath, self.tmpsf.filename)))
        self.tmpsf.refresh_from_db()
        self.assertEqual(self.tmpsf.servershare_id, self.ssnewstore.pk)
        self.assertEqual(self.tmpsf.path, self.oldds.storage_loc)
        
        # Clean up
        newdsr.delete()
