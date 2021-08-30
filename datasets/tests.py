import os
import json
from datetime import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User

from kantele import settings
from datasets import models as dm
from jobs import models as jm


class BaseDatasetTest(TestCase):
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
        self.ds1 = dm.Dataset.objects.create(date=self.p1.registered, runname=self.run1,
                datatype=self.dtype, storage_loc='testloc1/path/to/file')
        own1 = dm.DatasetOwner.objects.create(dataset=self.ds1, user=self.user)


class RenameProjectTest(BaseDatasetTest):
    def setUp(self):
        super().setUp()
        self.url = '/datasets/rename/project/'

    def test_no_ownership_fail(self):
        ####
        run = dm.RunName.objects.create(name='someoneelsesrun', experiment=self.exp1)
        ds = dm.Dataset.objects.create(date=self.p1.registered, runname=run,
                datatype=self.dtype, storage_loc='test')
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
        self.assertIn(f'cannot contain characters except {settings.ALLOWED_PROJEXPRUN_CHARS}', json.loads(resp.content)['error'])

    def test_rename_ok(self):
        newname = 'testnewname'
        resp = self.cl.post(self.url, content_type='application/json',
                data={'projid': self.p1.pk, 'newname': newname})
        self.assertEqual(resp.status_code, 200)
        renamejobs = jm.Job.objects.filter(funcname='rename_top_lvl_projectdir',
                kwargs={'proj_id': self.p1.pk, 'newname': newname}) 
        self.assertEqual(renamejobs.count(), 1)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.name, newname)


class MergeProjectsTest(BaseDatasetTest):
    def setUp(self):
        super().setUp()
        self.url = '/datasets/merge/projects/'
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
                datatype=self.dtype, storage_loc='test')
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
                datatype=self.dtype, storage_loc='testloc3')
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
                datatype=self.dtype, storage_loc=oldstorloc)
        dm.DatasetOwner.objects.create(dataset=ds2, user=self.user)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'projids': [self.p1.pk, self.p2.pk]})
        self.assertEqual(resp.status_code, 200)
        oldstorloc = ds2.storage_loc
        ds2.refresh_from_db()
        self.assertEqual(ds2.runname.experiment.project, self.ds1.runname.experiment.project)
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
                datatype=self.dtype, storage_loc=oldstorloc)
        own3 = dm.DatasetOwner.objects.create(dataset=ds3, user=self.user)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'projids': [self.p1.pk, self.p2.pk]})
        oldstorloc = ds3.storage_loc
        ds3.refresh_from_db()
        self.assertEqual(ds3.runname.experiment, self.ds1.runname.experiment)
        self.assertEqual(dm.Experiment.objects.filter(pk=exp3.pk).count(), 0)
        self.assertEqual(ds3.storage_loc, oldstorloc)
        renamejobs = jm.Job.objects.filter(funcname='rename_dset_storage_loc') 
        ds3jobs = renamejobs.filter(kwargs={'dset_id': ds3.pk, 
            'dstpath': os.path.join(self.p1.name, self.exp1.name, self.dtype.name, run3.name)})
        self.assertEqual(ds3jobs.count(), 1)
        self.assertEqual(renamejobs.count(), 1)
        self.assertEqual(dm.Project.objects.filter(pk=self.p2.pk).count(), 0)
