import os
import json
from time import sleep
from datetime import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.management import call_command

from kantele import settings
from kantele.tests import BaseTest, BaseIntegrationTest
from datasets import models as dm
from jobs import models as jm
from rawstatus import models as rm


class UpdateDatasetTest(BaseIntegrationTest):
    url = '/datasets/save/dataset/'

    def test_update_dset_newexp_location(self):
        newexpname = 'edited_exp'
        self.assertEqual(dm.Experiment.objects.filter(name=newexpname).count(), 0)
        resp = self.cl.post(self.url, content_type='application/json', data={
            'dataset_id': self.ds.pk, 'project_id': self.p1.pk, 'newexperimentname': newexpname,
            'runname': self.run1.name, 'datatype_id': self.dtype.pk, 'prefrac_id': False,
            'ptype_id': self.ptype.pk, 'externalcontact': self.contact.email})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(dm.Experiment.objects.filter(name=newexpname).count(), 1)
        self.assertTrue(os.path.exists(self.f3path))
        call_command('runjobs')
        sleep(3)
        self.assertFalse(os.path.exists(self.f3path))
        new_ds_loc = os.path.join(self.p1.name, newexpname, self.dtype.name, self.run1.name)
        self.assertNotEqual(self.ds.storage_loc, new_ds_loc)
        self.ds.refresh_from_db()
        self.assertEqual(self.ds.storage_loc, new_ds_loc)
        self.assertTrue(os.path.exists(os.path.join(settings.SHAREMAP[self.ds.storageshare.name],
            self.ds.storage_loc, self.f3sf.filename)))


class RenameProjectTest(BaseIntegrationTest):
    url = '/datasets/rename/project/'

    def test_no_ownership_fail(self):
        ####
        run = dm.RunName.objects.create(name='someoneelsesrun', experiment=self.exp1)
        ds = dm.Dataset.objects.create(date=self.p1.registered, runname=run,
                datatype=self.dtype, storage_loc='test', storageshare=self.ssnewstore)
        otheruser = User.objects.create(username='test', password='test')
        own = dm.DatasetOwner.objects.create(dataset=ds, user=otheruser)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'projid': self.p1.pk, 'newname': 'testnewp'})
        self.assertEqual(resp.status_code, 403)

    def test_id_name_fails(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'projid': self.p1.pk, 'newname': self.p1.name})
        self.assertEqual(resp.status_code, 403)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'projid': self.p1.pk+1000, 'newname': 'testnewname'})
        self.assertEqual(resp.status_code, 404)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'projid': self.p1.pk, 'newname': 'testnewname with spaces'})
        self.assertEqual(resp.status_code, 403)
        self.assertIn(f'cannot contain characters except {settings.ALLOWED_PROJEXPRUN_CHARS}',
                json.loads(resp.content)['error'])
        # existing proj name? proj name identical to old projname

    def test_rename_ok(self):
        newname = 'testnewname'
        self.assertEqual(dm.Project.objects.filter(name=newname).count(), 0)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'projid': self.p1.pk, 'newname': newname})
        self.assertEqual(resp.status_code, 200)
        renamejobs = jm.Job.objects.filter(funcname='rename_top_lvl_projectdir',
                kwargs={'proj_id': self.p1.pk, 'newname': newname}) 
        self.assertEqual(renamejobs.count(), 1)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.name, newname)
        self.assertTrue(os.path.exists(self.f3path))
        call_command('runjobs')
        sleep(3)
        self.assertFalse(os.path.exists(self.f3path))
        new_loc = os.path.join(newname, self.exp1.name, self.dtype.name, self.run1.name)
        self.assertNotEqual(self.ds.storage_loc, new_loc)
        self.ds.refresh_from_db()
        self.assertEqual(self.ds.storage_loc, new_loc)
        self.assertTrue(os.path.exists(os.path.join(settings.SHAREMAP[self.ds.storageshare.name],
            self.ds.storage_loc, self.f3sf.filename)))



class MergeProjectsTest(BaseTest):
    url = '/datasets/merge/projects/'

    def setUp(self):
        super().setUp()
        # make projects
        self.p2 = dm.Project.objects.create(name='p2', pi=self.pi)
        pt2 = dm.ProjType.objects.create(project=self.p2, ptype=self.ptype)
        self.exp2 = dm.Experiment.objects.create(name='e2', project=self.p2)

    def test_merge_fails(self):
        # GET req
        resp = self.cl.get(self.url)
        self.assertEqual(resp.status_code, 405)
        # No data
        resp = self.cl.post(self.url, content_type='application/json',
                data={})
        self.assertEqual(resp.status_code, 400)
        # Only one project
        resp = self.cl.post(self.url, content_type='application/json',
                data={'projids': [1]})
        self.assertEqual(resp.status_code, 400)
       
    def test_no_ownership_fail(self):
        run = dm.RunName.objects.create(name='someoneelsesrun', experiment=self.exp2)
        ds = dm.Dataset.objects.create(date=self.p2.registered, runname=run,
                datatype=self.dtype, storage_loc='test', storageshare=self.ssnewstore)
        otheruser = User.objects.create(username='test', password='test')
        own = dm.DatasetOwner.objects.create(dataset=ds, user=otheruser)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'projids': [self.p1.pk, self.p2.pk]})
        self.assertEqual(resp.status_code, 403)
        
    def test_dataset_exp_run_collision_fail(self):
        """When datasets of different projects have identical experiment and run names,
        we cannot merge projects"""
        exp3 = dm.Experiment.objects.create(name='e1', project=self.p2)
        run3 = dm.RunName.objects.create(name=self.run1.name, experiment=exp3)
        ds3 = dm.Dataset.objects.create(date=self.p2.registered, runname=run3,
                datatype=self.dtype, storage_loc='testloc3', storageshare=self.ssnewstore)
        dm.DatasetOwner.objects.create(dataset=ds3, user=self.user)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'projids': [self.p1.pk, self.p2.pk]})
        self.assertEqual(resp.status_code, 500)

    def test_merge_diff_exps(self):
        """
        assert ds1/ds2 under same project
        assert storage loc has been changed
        """
        run2 = dm.RunName.objects.create(name='run2', experiment=self.exp2)
        oldstorloc = 'testloc2'
        ds2 = dm.Dataset.objects.create(date=self.p2.registered, runname=run2,
                datatype=self.dtype, storage_loc=oldstorloc, storageshare=self.ssnewstore)
        dm.DatasetOwner.objects.create(dataset=ds2, user=self.user)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'projids': [self.p1.pk, self.p2.pk]})
        self.assertEqual(resp.status_code, 200)
        # Press merge button twice
        resp2 = self.cl.post(self.url, content_type='application/json',
                data={'projids': [self.p1.pk, self.p2.pk]})
        self.assertEqual(resp2.status_code, 400)
        
        oldstorloc = ds2.storage_loc
        ds2.refresh_from_db()
        self.assertEqual(ds2.runname.experiment.project, self.ds.runname.experiment.project)
        self.assertEqual(ds2.storage_loc, oldstorloc)
        renamejobs = jm.Job.objects.filter(funcname='rename_dset_storage_loc') 
        ds2jobs = renamejobs.filter(kwargs={'dset_id': ds2.pk,
            'dstpath': os.path.join(self.p1.name, self.exp2.name, self.dtype.name, run2.name)})
        self.assertEqual(ds2jobs.count(), 1)
        self.assertEqual(renamejobs.count(), 1)
        self.assertEqual(dm.Project.objects.filter(pk=self.p2.pk).count(), 0)

    def test_merge_identical_expnames(self):
        """
        assert ds1/ds2 under same project
        assert storage loc has been changed
        assert old exp has been deleted
        """
        exp3 = dm.Experiment.objects.create(name=self.exp1.name, project=self.p2)
        run3 = dm.RunName.objects.create(name='run3', experiment=exp3)
        oldstorloc = 'testloc3'
        ds3 = dm.Dataset.objects.create(date=self.p2.registered, runname=run3,
                datatype=self.dtype, storage_loc=oldstorloc, storageshare=self.ssnewstore)
        own3 = dm.DatasetOwner.objects.create(dataset=ds3, user=self.user)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'projids': [self.p1.pk, self.p2.pk]})
        oldstorloc = ds3.storage_loc
        ds3.refresh_from_db()
        self.assertEqual(ds3.runname.experiment, self.ds.runname.experiment)
        self.assertEqual(dm.Experiment.objects.filter(pk=exp3.pk).count(), 0)
        self.assertEqual(ds3.storage_loc, oldstorloc)
        renamejobs = jm.Job.objects.filter(funcname='rename_dset_storage_loc') 
        ds3jobs = renamejobs.filter(kwargs={'dset_id': ds3.pk, 
            'dstpath': os.path.join(self.p1.name, self.exp1.name, self.dtype.name, run3.name)})
        self.assertEqual(ds3jobs.count(), 1)
        self.assertEqual(renamejobs.count(), 1)
        self.assertEqual(dm.Project.objects.filter(pk=self.p2.pk).count(), 0)
