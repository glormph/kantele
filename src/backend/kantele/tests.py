# Integration tests, including storage files etc
import os
from time import sleep

from django.contrib.auth.models import User
from django.test import LiveServerTestCase, Client
from django.utils import timezone
from django.core.management import call_command

from kantele import settings
from datasets import models as dm
from rawstatus import models as rm
from jobs import models as jm


class BaseIntegrationTest(LiveServerTestCase):
    port = 80
    host = '0.0.0.0'

    def setUp(self):
        self.cl = Client()
        username='testuser'
        email = 'test@test.com'
        password='12345'
        self.user = User(username=username, email=email)
        self.user.set_password(password)
        self.user.save() 
        login = self.cl.login(username=username, password=password)
        # make projects
        qdt = dm.Datatype.objects.create(name='Quantitative proteomics')
        self.ptype = dm.ProjectTypeName.objects.create(name='testpt')
        self.pi = dm.PrincipalInvestigator.objects.create(name='testpi')
        self.dtype = dm.Datatype.objects.create(name='dttest')
        self.p1 = dm.Project.objects.create(name='p1', pi=self.pi)
        pt1 = dm.ProjType.objects.create(project=self.p1, ptype=self.ptype)
        self.exp1 = dm.Experiment.objects.create(name='e1', project=self.p1)
        self.run1 = dm.RunName.objects.create(name='run1', experiment=self.exp1)
        self.newfserver = rm.FileServer.objects.create(name='server1', uri='s1.test')
        self.sstmp = rm.ServerShare.objects.create(name=settings.TMPSHARENAME, server=self.newfserver,
                share='/home/testtmp')
        self.ssnewstore = rm.ServerShare.objects.create(name=settings.PRIMARY_STORAGESHARENAME,
                server=self.newfserver, share='/home/storage')
        self.oldfserver = rm.FileServer.objects.create(name='oldserver', uri='s0.test')
        self.ssoldstorage = rm.ServerShare.objects.create(name=settings.STORAGESHARENAMES[0],
                server=self.oldfserver, share='/home/storage')

        dscomp = dm.DatasetComponent.objects.create(name='files')
        self.dtcomp = dm.DatatypeComponent.objects.create(datatype=self.dtype, component=dscomp)
    def test_move_dataset_old_new_storage(self):
        storloc = os.path.join(self.p1.name, self.exp1.name, self.run1.name)
        self.ds = dm.Dataset.objects.create(date=self.p1.registered, runname=self.run1,
                datatype=self.dtype, storageshare=self.ssoldstorage, storage_loc=storloc)
        dtcstate = dm.DatasetComponentState.objects.create(dataset=self.ds, dtcomp=self.dtcomp, state='OK')
        self.ft = rm.StoredFileType.objects.create(name='testft', filetype='tst')
        self.prod = rm.Producer.objects.create(name='prod1', client_id='abcdefg', shortname='p1')
        own1 = dm.DatasetOwner.objects.create(dataset=self.ds, user=self.user)
        oldfn = 'raw1'
        oldfpath = os.path.join(settings.SHAREMAP[self.ssoldstorage.name], storloc)
        oldsize = os.path.getsize(os.path.join(oldfpath, oldfn))
        oldraw = rm.RawFile.objects.create(name='file1', producer=self.prod,
                source_md5='52416cc60390c66e875ee6ed8e03103a',
                size=oldsize, date=timezone.now(), claimed=True)
        dsr = dm.DatasetRawFile.objects.create(dataset=self.ds, rawfile=oldraw)
        oldsf = rm.StoredFile.objects.create(rawfile=oldraw, filename=oldfn, servershare=self.ssoldstorage,
                path=storloc, md5=oldraw.source_md5, checked=True, filetype=self.ft)

        newfn = 'raw2'
        newfpathfn = os.path.join(settings.SHAREMAP[self.sstmp.name], newfn)
        newsize = os.path.getsize(newfpathfn)
        newraw = rm.RawFile.objects.create(name=newfn, producer=self.prod,
                source_md5='e55c60b56dbafe0d4e748e386cda447c',
                size=newsize, date=timezone.now(), claimed=False)
        newsf = rm.StoredFile.objects.create(rawfile=newraw, filename=newfn, servershare=self.sstmp,
                path='', md5=newraw.source_md5, checked=True, filetype=self.ft)

        url = '/datasets/save/files/'
        postdata = {'dataset_id': self.ds.pk, 'added_files': {'fn2': {'id': newraw.pk}}, 'removed_files': {}}
        resp = self.cl.post(url, content_type='application/json', data=postdata)
        self.assertEqual(resp.status_code, 200)
        # call job runner to run rsync and move file. They do not wait
        call_command('runjobs')
        sleep(3)
        self.assertFalse(os.path.exists(oldfpath))
        newdspath = os.path.join(settings.SHAREMAP[self.ssnewstore.name], storloc)
        self.assertTrue(os.path.exists(os.path.join(newdspath, oldfn)))
        self.assertTrue(os.path.exists(os.path.join(newdspath, newfn)))
        self.assertEqual(dm.DatasetRawFile.objects.filter(dataset=self.ds, rawfile=newraw).count(), 1)
        newraw.refresh_from_db()
        self.assertTrue(newraw.claimed)
        self.ds.refresh_from_db()
        newsf.refresh_from_db()
        self.assertEqual(newsf.servershare_id, self.ssnewstore.pk)
        oldsf.refresh_from_db()
        self.assertEqual(oldsf.servershare_id, self.ssnewstore.pk)
        self.assertEqual(self.ds.storageshare_id, self.ssnewstore.pk)
        self.assertEqual(self.ds.storage_loc, storloc)
