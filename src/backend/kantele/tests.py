# Integration tests, including storage files etc
import os
import shutil
from time import sleep
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, LiveServerTestCase, Client
from django.utils import timezone
from django.core.management import call_command

from kantele import settings
from datasets import models as dm
from rawstatus import models as rm
from jobs import models as jm
from analysis import models as am


# FIXME
# This is mainly fixtures and its getting out of hand
# We need to separate them better

# Django flushes DB between tests, so we dont need get_or_create, but theres a lot non shared


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

        # Species / sampletype fill
        self.spec1, _ = dm.Species.objects.get_or_create(linnean='species1', popname='Spec1')
        self.spec2, _ = dm.Species.objects.get_or_create(linnean='species2', popname='Spec2')
        self.samtype1, _ = dm.SampleMaterialType.objects.get_or_create(name='sampletype1')
        self.samtype2, _ = dm.SampleMaterialType.objects.get_or_create(name='sampletype2')


        # Datasets/projects prep
        self.dtype, _ = dm.Datatype.objects.get_or_create(name='dtype1')
        self.dtcompdef = dm.DatatypeComponent.objects.create(datatype=self.dtype, component=dm.DatasetUIComponent.DEFINITION)
        self.dtcompfiles = dm.DatatypeComponent.objects.create(datatype=self.dtype, component=dm.DatasetUIComponent.FILES)
        self.dtcompsamples = dm.DatatypeComponent.objects.create(datatype=self.dtype, component=dm.DatasetUIComponent.SAMPLES)
        qdt, _ = dm.Datatype.objects.get_or_create(name='Quantitative proteomics')
        self.ptype, _ = dm.ProjectTypeName.objects.get_or_create(name='testpt')
        self.pi, _ = dm.PrincipalInvestigator.objects.get_or_create(name='testpi')

        # File prep, producers etc
        self.ft, _ = rm.StoredFileType.objects.get_or_create(name='testft', filetype='tst',
                is_rawdata=True)
        self.prod, _ = rm.Producer.objects.get_or_create(name='prod1', client_id='abcdefg', shortname='p1', internal=True)
        msit, _ = rm.MSInstrumentType.objects.get_or_create(name='test')
        rm.MSInstrument.objects.get_or_create(producer=self.prod, instrumenttype=msit,
                filetype=self.ft)
        self.qt, _ = dm.QuantType.objects.get_or_create(name='testqt', shortname='testqtplex')
        self.qch, _ = dm.QuantChannel.objects.get_or_create(name='thech')
        self.qtch, _ = dm.QuantTypeChannel.objects.get_or_create(quanttype=self.qt, channel=self.qch) 
        self.lfqt, _ = dm.QuantType.objects.get_or_create(name='labelfree', shortname='lf')

        # Project/dset on new storage
        self.p1, _ = dm.Project.objects.get_or_create(name='p1', pi=self.pi)
        self.projsam1, _ = dm.ProjectSample.objects.get_or_create(sample='sample1', project=self.p1)
        dm.SampleMaterial.objects.create(sample=self.projsam1, sampletype=self.samtype1)
        dm.SampleSpecies.objects.create(sample=self.projsam1, species=self.spec1)
        dm.ProjType.objects.get_or_create(project=self.p1, ptype=self.ptype)
        self.exp1, _ = dm.Experiment.objects.get_or_create(name='e1', project=self.p1)
        self.run1, _ = dm.RunName.objects.get_or_create(name='run1', experiment=self.exp1)
        self.storloc = os.path.join(self.p1.name, self.exp1.name, self.dtype.name, self.run1.name)
        self.ds, _ = dm.Dataset.objects.update_or_create(date=self.p1.registered, runname=self.run1,
                datatype=self.dtype, defaults={'storageshare': self.ssnewstore, 
                    'storage_loc': self.storloc})
        dm.DatasetComponentState.objects.create(dataset=self.ds, state=dm.DCStates.OK, dtcomp=self.dtcompfiles)
        dm.DatasetComponentState.objects.create(dataset=self.ds, state=dm.DCStates.OK, dtcomp=self.dtcompsamples)
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
        self.qcs, _  = dm.QuantChannelSample.objects.get_or_create(dataset=self.ds, channel=self.qtch,
                projsample=self.projsam1)
        dm.QuantDataset.objects.get_or_create(dataset=self.ds, quanttype=self.qt)
        dm.DatasetSample.objects.create(dataset=self.ds, projsample=self.projsam1)

        # Pwiz/mzml
        self.pset = am.ParameterSet.objects.create(name='pset_base')
        self.nfw = am.NextflowWorkflowRepo.objects.create(
                description='repo_base desc', repo='repo_base')
        wfv = am.NextflowWfVersionParamset.objects.create(update='pwiz wfv base',
                commit='pwiz ci base', filename='pwiz.nf', nfworkflow=self.nfw,
                paramset=self.pset, nfversion='', active=True)
        self.pwiz = am.Proteowizard.objects.create(version_description='pwversion desc1',
                container_version='', nf_version=wfv)
        self.f3sfmz = rm.StoredFile.objects.create(rawfile=self.f3raw, filename=f'{fn3}.mzML',
                md5='md5_for_f3sf_mzml', filetype=self.ft, servershare=self.ssnewstore,
                path=self.storloc, checked=True)
        am.MzmlFile.objects.create(sfile=self.f3sfmz, pwiz=self.pwiz)

        # Project/dataset/files on old storage
        oldfn = 'raw1'
        self.oldp, _ = dm.Project.objects.get_or_create(name='oldp', pi=self.pi)
        self.projsam2, _ = dm.ProjectSample.objects.get_or_create(sample='sample2', project=self.oldp)
        dm.SampleMaterial.objects.create(sample=self.projsam2, sampletype=self.samtype2)
        dm.SampleSpecies.objects.create(sample=self.projsam2, species=self.spec2)
        dm.ProjType.objects.get_or_create(project=self.oldp, ptype=self.ptype)
        self.oldexp, _ = dm.Experiment.objects.get_or_create(name='olde', project=self.oldp)
        self.oldrun, _ = dm.RunName.objects.get_or_create(name='run1', experiment=self.oldexp)
        self.oldstorloc = os.path.join(self.oldp.name, self.oldexp.name, self.oldrun.name)
        self.oldds, _ = dm.Dataset.objects.update_or_create(date=self.oldp.registered,
                runname=self.oldrun, datatype=self.dtype, defaults={
                    'storageshare': self.ssoldstorage, 'storage_loc': self.oldstorloc})
        dm.QuantDataset.objects.get_or_create(dataset=self.oldds, quanttype=self.lfqt)
        dm.DatasetComponentState.objects.create(dataset=self.oldds, dtcomp=self.dtcompfiles, state=dm.DCStates.OK)
        dm.DatasetComponentState.objects.create(dataset=self.oldds, dtcomp=self.dtcompsamples, state=dm.DCStates.OK)
        self.contact, _ = dm.ExternalDatasetContact.objects.get_or_create(dataset=self.oldds,
                email='contactname')
        dm.DatasetOwner.objects.get_or_create(dataset=self.oldds, user=self.user)
        self.oldfpath = os.path.join(settings.SHAREMAP[self.ssoldstorage.name], self.oldstorloc)
        oldsize = os.path.getsize(os.path.join(self.oldfpath, oldfn))
        self.oldraw, _ = rm.RawFile.objects.get_or_create(name=oldfn, producer=self.prod,
                source_md5='old_to_new_fakemd5', size=oldsize, defaults={'date': timezone.now(),
                    'claimed': True})
        self.olddsr, _ = dm.DatasetRawFile.objects.get_or_create(dataset=self.oldds, rawfile=self.oldraw)
        self.oldsf, _ = rm.StoredFile.objects.update_or_create(rawfile=self.oldraw, filename=oldfn,
                    md5=self.oldraw.source_md5, filetype=self.ft,
                    defaults={'servershare': self.ssoldstorage, 'path': self.oldstorloc, 
                        'checked': True})
        self.oldqsf = dm.QuantSampleFile.objects.create(rawfile=self.olddsr, projsample=self.projsam2)

        # Tmp rawfile
        tmpfn = 'raw2'
        tmpfpathfn = os.path.join(settings.SHAREMAP[self.sstmp.name], tmpfn)
        tmpsize = os.path.getsize(tmpfpathfn)
        self.tmpraw, _ = rm.RawFile.objects.get_or_create(name=tmpfn, producer=self.prod,
                source_md5='tmpraw_fakemd5', size=tmpsize, defaults={'date': timezone.now(),
                    'claimed': False})
        self.tmpsf, _ = rm.StoredFile.objects.update_or_create(rawfile=self.tmpraw,
                md5=self.tmpraw.source_md5, defaults={'filename': tmpfn, 'servershare': self.sstmp,
                    'path': '', 'checked': True, 'filetype': self.ft})

        # FIXME should go to analysis? Maybe reuse in home etc views
        # Library files, for use as input, so claimed and ready
        self.libraw, _ = rm.RawFile.objects.update_or_create(name='libfiledone',
                producer=self.prod, source_md5='libfilemd5',
                size=100, defaults={'claimed': True, 'date': timezone.now()})

        self.sflib, _ = rm.StoredFile.objects.update_or_create(rawfile=self.libraw,
                md5=self.libraw.source_md5, filetype=self.ft, defaults={'checked': True, 
                    'filename': self.libraw.name, 'servershare': self.sstmp, 'path': ''})
        self.lf, _ = am.LibraryFile.objects.get_or_create(sfile=self.sflib, description='This is a libfile')

        # User files for input
        self.usrfraw, _ = rm.RawFile.objects.update_or_create(name='usrfiledone',
                producer=self.prod, source_md5='usrfmd5', size=100, 
                defaults={'claimed': True, 'date': timezone.now()})
        self.uft, _ = rm.StoredFileType.objects.get_or_create(name='ufileft', filetype='tst',
                is_rawdata=False)
        self.sfusr, _ = rm.StoredFile.objects.update_or_create(rawfile=self.usrfraw,
                md5=self.usrfraw.source_md5, filetype=self.uft,
                defaults={'filename': self.usrfraw.name, 'servershare': self.sstmp,
                    'path': '', 'checked': True})
        self.usedtoken, _ = rm.UploadToken.objects.update_or_create(user=self.user, token='usrffailtoken',
                expired=False, producer=self.prod, filetype=self.uft, defaults={
                    'expires': timezone.now() + timedelta(1)})
        self.userfile, _ = rm.UserFile.objects.get_or_create(sfile=self.sfusr,
                description='This is a userfile', upload=self.usedtoken)

        # Analysis files
        self.anaprod = rm.Producer.objects.create(name='analysisprod', client_id=settings.ANALYSISCLIENT_APIKEY, shortname='pana')
        self.ana_raw, _ = rm.RawFile.objects.get_or_create(name='ana_file', producer=self.anaprod, source_md5='kjlmnop1234',
                size=100, defaults={'date': timezone.now(), 'claimed': True})
        self.anasfile, _ = rm.StoredFile.objects.get_or_create(rawfile=self.ana_raw,
                filetype_id=self.ft.id, defaults={'filename': self.ana_raw.name,
                    'servershare': self.sstmp, 'path': '', 'md5': self.ana_raw.source_md5})
        self.ana_raw2, _ = rm.RawFile.objects.get_or_create(name='ana_file2', producer=self.anaprod,
                source_md5='anarawabc1234', size=100, defaults={'date': timezone.now(), 'claimed': True})
        self.anasfile2, _ = rm.StoredFile.objects.get_or_create(rawfile=self.ana_raw2,
                filetype_id=self.ft.id, defaults={'filename': self.ana_raw2.name, 'filetype': self.ft,
                    'servershare_id': self.sstmp.id, 'path': '', 'md5': self.ana_raw2.source_md5})


class ProcessJobTest(BaseTest):

    def setUp(self):
        super().setUp()
        self.job = self.jobclass(1)

    def check(self, expected_tasks):
        self.assertEqual(self.job.run_tasks, expected_tasks)


class BaseIntegrationTest(LiveServerTestCase):
    # use a live server so that jobrunner can interface with it (otherwise only dummy
    # test client can do that)
    port = 80
    host = '0.0.0.0'
    jobrun_timeout = 2

    def setUp(self):
        BaseTest.setUp(self)

    def post_json(self, data):
        return self.cl.post(self.url, content_type='application/json', data=data)

    def run_job(self):
        '''Call run jobs, then sleep to make tasks do their work'''
        call_command('runjobs')
        sleep(self.jobrun_timeout)


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
        self.run_job()
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
        self.run_job()
        self.assertTrue(os.path.exists(os.path.join(newdspath, self.tmpsf.filename)))
        self.tmpsf.refresh_from_db()
        self.assertEqual(self.tmpsf.servershare_id, self.ssnewstore.pk)
        self.assertEqual(self.tmpsf.path, self.oldds.storage_loc)
        
        # Clean up
        newdsr.delete()
