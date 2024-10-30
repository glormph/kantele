import os
from django.utils import timezone

from kantele import settings
from kantele.tests import BaseTest 
from analysis import models as am
from rawstatus import models as rm
from datasets import models as dm
from jobs import models as jm
from jobs.jobs import Jobstates


class MzmlTests(BaseTest):
    def setUp(self):
        super().setUp()
        # workflow stuff
        ps, _ = am.ParameterSet.objects.get_or_create(name='')
        nfw, _ = am.NextflowWorkflowRepo.objects.get_or_create(description='', repo='')
        self.nfwv, _ = am.NextflowWfVersionParamset.objects.get_or_create(update='', commit='', filename='',
                nfworkflow=nfw, paramset=ps, nfversion='', active=True)
        self.pw, _ = am.Proteowizard.objects.get_or_create(version_description='',
                container_version='', nf_version=self.nfwv, is_docker=True)

        # Stored files input
        self.ssmzml, _ = rm.ServerShare.objects.get_or_create(name=settings.MZMLINSHARENAME, 
                server=self.newfserver, share='/home/mzmls')
        self.ft, _ = rm.StoredFileType.objects.get_or_create(name='Thermo raw', filetype='raw')
        self.prodqe, _ = rm.Producer.objects.get_or_create(name='qe_prod', client_id='abcdefg',
                shortname='p1')
        self.prodtims, _ = rm.Producer.objects.get_or_create(name='tims_prod', client_id='hijklm',
                shortname='p2')
        self.tims, _ = rm.MSInstrumentType.objects.get_or_create(name='timstof')
        self.qe, _ = rm.MSInstrumentType.objects.get_or_create(name='qe')
        instqe, _ = rm.MSInstrument.objects.get_or_create(producer=self.prodqe,
                instrumenttype=self.qe, filetype=self.ft)
        insttims, _ = rm.MSInstrument.objects.get_or_create(producer=self.prodtims,
                instrumenttype=self.tims, filetype=self.ft)
        own1, _ = dm.DatasetOwner.objects.get_or_create(dataset=self.ds, user=self.user)
        self.run = dm.RunName.objects.create(name=self.id(), experiment=self.exp1)
        self.storloc = os.path.join(self.p1.name, self.exp1.name, self.run.name) 
        self.ds = dm.Dataset.objects.create(date=self.p1.registered, runname=self.run,
                datatype=self.dtype, storageshare=self.ssnewstore, storage_loc=self.storloc)
        dm.QuantDataset.objects.get_or_create(dataset=self.ds, quanttype=self.qt)
        self.qeraw, _ = rm.RawFile.objects.update_or_create(name='file1', defaults={
            'producer': self.prodqe, 'source_md5': '52416cc60390c66e875ee6ed8e03103a',
            'size': 100, 'date': timezone.now(), 'claimed': True})
        self.qesf, _ = rm.StoredFile.objects.update_or_create(rawfile=self.qeraw, 
                filename=self.qeraw.name, defaults={'servershare': self.ds.storageshare,
                    'path': self.storloc, 'md5': self.qeraw.source_md5, 'checked': True,
                    'filetype': self.ft})
        self.timsraw = rm.RawFile.objects.create(name='file2', producer=self.prodtims,
                source_md5='timsmd4',
                size=100, date=timezone.now(), claimed=True)
        dm.DatasetRawFile.objects.update_or_create(rawfile=self.qeraw, defaults={'dataset': self.ds})


class TestCreateMzmls(MzmlTests):
    url = '/createmzml/'

    def test_fail_requests(self):
        # GET
        resp = self.cl.get(self.url)
        self.assertEqual(resp.status_code, 405)
        # wrong  keys
        resp = self.cl.post(self.url, content_type='application/json', data={'hello': 'test'})
        self.assertEqual(resp.status_code, 400)
        # dset does not exist
        resp = self.cl.post(self.url, content_type='application/json', data={'pwiz_id': self.pw.pk,
            'dsid': 10000})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('does not exist or is deleted', resp.json()['error'])
        # dset with diff raw files
        timsdsr = dm.DatasetRawFile.objects.create(dataset=self.ds, rawfile=self.timsraw)
        resp = self.cl.post(self.url, content_type='application/json', data={'pwiz_id': self.pw.pk,
            'dsid': self.ds.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('contains data from multiple instrument types', resp.json()['error'])
        timsdsr.delete()
    
    def test_existing_mzmls(self):
        exist_mzml = am.MzmlFile.objects.create(sfile=self.qesf, pwiz=self.pw)
        resp = self.cl.post(self.url, content_type='application/json', data={'pwiz_id': self.pw.pk,
            'dsid': self.ds.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('already has existing mzML files of that proteowizard', resp.json()['error'])
        exist_mzml.delete()

    def test_other_pwiz(self):
        '''Test if old pwiz existing files get purge job BEFORE launching new job'''
        newpw, _ = am.Proteowizard.objects.get_or_create(version_description='newer', container_version='', nf_version=self.nfwv)
        exist_mzml = am.MzmlFile.objects.create(sfile=self.qesf, pwiz=newpw)
        resp = self.cl.post(self.url, content_type='application/json', data={'pwiz_id': self.pw.pk,
            'dsid': self.ds.pk})
        self.assertEqual(resp.status_code, 200)
        purgej = jm.Job.objects.filter(funcname='delete_mzmls_dataset').last()
        self.assertEqual(purgej.kwargs, {'dset_id': self.ds.pk, 'pwiz_id': newpw.pk})
        self.assertEqual(purgej.state, Jobstates.PENDING)
        j = jm.Job.objects.filter(funcname='convert_dataset_mzml').last()
        self.assertEqual(j.state, Jobstates.PENDING)
        exp_kw  = {'options': [], 'filters': ['"peakPicking true 2"', '"precursorRefine"'], 
                'dset_id': self.ds.pk, 'pwiz_id': self.pw.pk}
        for k, val in exp_kw.items():
            self.assertEqual(j.kwargs[k], val)
        self.qesf.refresh_from_db()
        self.assertTrue(self.qesf.deleted)
        self.assertEqual(jm.Job.objects.filter(funcname='move_dset_servershare', kwargs__dset_id=self.ds.pk).count(), 0)
        exist_mzml.delete()

    def test_create_mzml_qe(self):
        postdata = {'pwiz_id': self.pw.pk, 'dsid': self.ds.pk}
        resp = self.cl.post(self.url, content_type='application/json', data=postdata)
        self.assertEqual(resp.status_code, 200)
        j = jm.Job.objects.last()
        self.assertEqual(j.funcname, 'convert_dataset_mzml')
        exp_kw  = {'options': [], 'filters': ['"peakPicking true 2"', '"precursorRefine"'], 
                'dset_id': self.ds.pk, 'pwiz_id': self.pw.pk}
        for k, val in exp_kw.items():
            self.assertEqual(j.kwargs[k], val)
        self.assertEqual(jm.Job.objects.filter(funcname='move_dset_servershare',
            kwargs__dset_id=self.ds.pk).count(), 0)

    def test_create_mzml_tims(self):
        self.qeraw.producer = self.prodtims
        self.qeraw.save()
        postdata = {'pwiz_id': self.pw.pk, 'dsid': self.ds.pk}
        resp = self.cl.post(self.url, content_type='application/json', data=postdata)
        self.assertEqual(resp.status_code, 200)
        j = jm.Job.objects.last()
        self.assertEqual(j.funcname, 'convert_dataset_mzml')
        exp_kw  = {'options': ['combineIonMobilitySpectra'], 'filters': ['"peakPicking true 2"', '"precursorRefine"', '"scanSumming precursorTol=0.02 scanTimeTol=10 ionMobilityTol=0.1"'], 
                'dstshare_id': self.ssmzml.pk, 'dset_id': self.ds.pk, 'pwiz_id': self.pw.pk}
        for k, val in exp_kw.items():
            self.assertEqual(j.kwargs[k], val)
        self.assertEqual(jm.Job.objects.filter(funcname='move_dset_servershare',
            kwargs__dset_id=self.ds.pk).count(), 0)

    def test_with_filemove(self):
        # Create new dataset on old storage proj that can be mock-"moved"
        ds = self.ds
        ds.pk = None
        moverun = dm.RunName.objects.create(name=self.id(), experiment=self.oldexp)
        ds.storageshare = self.ssoldstorage
        ds.runname = moverun
        ds.storage_loc = 'test_with_filemove'
        ds.save()
        # Add file to mzML
        qeraw = self.qeraw
        qeraw.pk, qeraw.source_md5 = None, 'test_with_filemove_bcd1234'
        qeraw.save()
        dm.DatasetRawFile.objects.update_or_create(rawfile=qeraw, defaults={'dataset': ds})
        qesf = self.qesf
        qesf.pk, qesf.md5, qeraw.source_md5
        qesf.path, qesf.servershare_id = ds.storage_loc, ds.storageshare_id
        qesf.rawfile, qesf.filename = qeraw, qeraw.name
        qesf.save()
        postdata = {'pwiz_id': self.pw.pk, 'dsid': ds.pk}
        resp = self.cl.post(self.url, content_type='application/json', data=postdata)
        self.assertEqual(resp.status_code, 200)
        j = jm.Job.objects.last()
        self.assertEqual(j.funcname, 'convert_dataset_mzml')
        exp_kw  = {'options': [], 'filters': ['"peakPicking true 2"', '"precursorRefine"'], 
                'dstshare_id': self.ssmzml.pk, 'dset_id': ds.pk, 'pwiz_id': self.pw.pk}
        for k, val in exp_kw.items():
            self.assertEqual(j.kwargs[k], val)
        self.assertEqual(jm.Job.objects.filter(funcname='move_dset_servershare',
            kwargs__dset_id=ds.pk).count(), 1)
        # cleanup, this should also remove dset
        # FIXME why?
        #moverun.delete()


class TestRefineMzmls(MzmlTests):
    url = '/refinemzml/'

    def setUp(self):
        super().setUp()
        dbft = rm.StoredFileType.objects.create(name='database', filetype='tst', is_rawdata=False)
        dbraw = rm.RawFile.objects.create(name='db.fa', producer=self.prod, source_md5='db.famd5',
                size=100, date=timezone.now(), claimed=True)
        self.dbsf = rm.StoredFile.objects.create(rawfile=dbraw, filename=dbraw.name,
                    md5=dbraw.source_md5, filetype=dbft, servershare=self.ssnewstore,
                    path=self.storloc, checked=True)
        self.refinewf = am.NextflowWfVersionParamset.objects.create(update='refine wf',
                commit='refine ci', filename='refine.nf', nfworkflow=self.nfw, paramset=self.pset, 
                nfversion='', active=True)
        wf = am.UserWorkflow.objects.create(name='refine', wftype=am.UserWorkflow.WFTypeChoices.SPEC,
                public=False)
        wf.nfwfversionparamsets.add(self.refinewf)
        
    def test_fail_requests(self):
        # GET
        resp = self.cl.get(self.url)
        self.assertEqual(resp.status_code, 405)
        # wrong  keys
        resp = self.cl.post(self.url, content_type='application/json', data={'hello': 'test'})
        self.assertEqual(resp.status_code, 400)
        # dset does not exist
        resp = self.cl.post(self.url, content_type='application/json', data={'dsid': 10000})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('does not exist or is deleted', resp.json()['error'])
        dm.DatasetRawFile.objects.create(dataset=self.ds, rawfile=self.timsraw)
        resp = self.cl.post(self.url, content_type='application/json', data={'pwiz_id': self.pw.pk,
            'dsid': self.ds.pk, 'dbid': self.sflib.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('contains data from multiple instrument types', resp.json()['error'])

    def test_existing_mzmls_no_db(self):
        # no mzMLs exist yet
        resp = self.cl.post(self.url, content_type='application/json', data={'pwiz_id': self.pw.pk,
            'dsid': self.ds.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('Need to create normal mzMLs', resp.json()['error'])

        # Not passed a db
        am.MzmlFile.objects.create(sfile=self.qesf, pwiz=self.pw)
        resp = self.cl.post(self.url, content_type='application/json', data={'pwiz_id': self.pw.pk,
            'dsid': self.ds.pk})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual('Must pass a database to refine with', resp.json()['error'])

        # refined exists already
        refinedsf = rm.StoredFile.objects.create(rawfile=self.qeraw, filename=f'{self.qeraw.name}_refined',
                servershare=self.ds.storageshare, path=self.storloc, md5='refined_md5', checked=True, filetype=self.ft)
        am.MzmlFile.objects.create(sfile=refinedsf, pwiz=self.pw, refined=True)
        resp = self.cl.post(self.url, content_type='application/json', data={'dsid': self.ds.pk})
        self.assertEqual(resp.status_code, 403)

    def do_refine(self, ds):
        resp = self.cl.post(self.url, content_type='application/json', data={'dsid': ds.pk,
            'dbid': self.dbsf.pk, 'wfid': self.refinewf.pk})
        self.assertEqual(resp.status_code, 200)
        j = jm.Job.objects.last()
        self.assertEqual(j.funcname, 'refine_mzmls')
        exp_kw = {'dset_id': self.ds.pk, 'wfv_id': self.refinewf.pk,
                'dbfn_id': self.dbsf.pk, 'dstshare_id': self.ssmzml.pk,
                'qtype': self.ds.quantdataset.quanttype.shortname}
        for k, val in exp_kw.items():
            self.assertEqual(j.kwargs[k], val)

    def test_refine_mzml(self):
        '''Do a refine, test its correctness, then make sure there is no dataset servershare
        move on the current dataset, unlike the test_with_filemove (old data to new share)'''
        am.MzmlFile.objects.create(sfile=self.qesf, pwiz=self.pw)
        self.do_refine(self.ds)
        self.assertEqual(jm.Job.objects.filter(funcname='move_dset_servershare',
            kwargs__dset_id=self.ds.pk).count(), 0)

    def test_with_filemove(self):
        # Create new dataset on old storage proj that can be mock-"moved"
        moverun = dm.RunName.objects.create(name='test_with_filemove_loc', experiment=self.oldexp)
        ds = self.ds
        ds.storage_loc = moverun.name
        ds.pk = None
        ds.storageshare = self.ssoldstorage
        ds.runname = moverun
        ds.save()
        dm.QuantDataset.objects.get_or_create(dataset=ds, quanttype=self.qt)
        # Add raw files (pk=None, save -> copy original object)
        qeraw = self.qeraw
        qeraw.pk, qeraw.source_md5 = None, 'refine_test_with_filemove'
        qeraw.save()
        dm.DatasetRawFile.objects.create(rawfile=qeraw, dataset=ds)
        qesf = self.qesf
        qesf.pk, qesf.md5 = None, qeraw.source_md5
        qesf.path, qesf.servershare_id = ds.storage_loc, ds.storageshare_id
        qesf.rawfile, qesf.filename = qeraw, qeraw.name
        qesf.save()
        am.MzmlFile.objects.create(sfile=qesf, pwiz=self.pw)
        self.do_refine(ds)
        self.assertEqual(jm.Job.objects.filter(funcname='move_dset_servershare',
            kwargs__dset_id=ds.pk).count(), 1)
