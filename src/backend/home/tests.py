import os
from django.utils import timezone

from kantele import settings
from kantele.tests import BaseTest 
from analysis import models as am
from rawstatus import models as rm
from datasets import models as dm
from jobs import models as jm


class MzmlTests(BaseTest):
    def setUp(self):
        super().setUp()
        # workflow stuff
        ps, _ = am.ParameterSet.objects.get_or_create(name='')
        nfw, _ = am.NextflowWorkflow.objects.get_or_create(description='', repo='')
        self.nfwv, _ = am.NextflowWfVersion.objects.get_or_create(update='', commit='', filename='',
                nfworkflow=nfw, paramset=ps, kanteleanalysis_version=1, nfversion='')
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
        newpw, _ = am.Proteowizard.objects.get_or_create(version_description='newer', container_version='', nf_version=self.nfwv)
        exist_mzml = am.MzmlFile.objects.create(sfile=self.qesf, pwiz=newpw)
        resp = self.cl.post(self.url, content_type='application/json', data={'pwiz_id': self.pw.pk,
            'dsid': self.ds.pk})
        self.assertEqual(resp.status_code, 200)
        j = jm.Job.objects.last()
        self.assertEqual(j.funcname, 'convert_dataset_mzml')
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
        # Delete afterwards so the count job tests dont go bad between tests
        moverun = dm.RunName.objects.create(name=self.id(), experiment=self.oldexp)
        self.ds.storageshare = self.ssoldstorage
        self.ds.runname = moverun
        self.ds.save()
        postdata = {'pwiz_id': self.pw.pk, 'dsid': self.ds.pk}
        resp = self.cl.post(self.url, content_type='application/json', data=postdata)
        self.assertEqual(resp.status_code, 200)
        j = jm.Job.objects.last()
        self.assertEqual(j.funcname, 'convert_dataset_mzml')
        exp_kw  = {'options': [], 'filters': ['"peakPicking true 2"', '"precursorRefine"'], 
                'dstshare_id': self.ssmzml.pk, 'dset_id': self.ds.pk, 'pwiz_id': self.pw.pk}
        for k, val in exp_kw.items():
            self.assertEqual(j.kwargs[k], val)
        self.assertEqual(jm.Job.objects.filter(funcname='move_dset_servershare',
            kwargs__dset_id=self.ds.pk).count(), 1)
        # cleanup, this should also remove dset
        moverun.delete()


class TestRefineMzmls(MzmlTests):
    url = '/refinemzml/'

    def setUp(self):
        super().setUp()
        qt = dm.QuantType.objects.create(name='testqt', shortname='tqt')
        dm.QuantDataset.objects.create(dataset=self.ds, quanttype=qt)

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
            'dsid': self.ds.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('contains data from multiple instrument types', resp.json()['error'])

    def test_existing_mzmls(self):
        # no mzMLs exist yet
        resp = self.cl.post(self.url, content_type='application/json', data={'pwiz_id': self.pw.pk,
            'dsid': self.ds.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('Need to create normal mzMLs', resp.json()['error'])

        # refined exists already
        refinedsf = rm.StoredFile.objects.create(rawfile=self.qeraw, filename=self.qeraw.name, servershare=self.ds.storageshare,
                path=self.storloc, md5='refined_md5', checked=True, filetype=self.ft)
        am.MzmlFile.objects.create(sfile=refinedsf, pwiz=self.pw, refined=True)
        am.MzmlFile.objects.create(sfile=self.qesf, pwiz=self.pw)
        resp = self.cl.post(self.url, content_type='application/json', data={'dsid': self.ds.pk})
        self.assertEqual(resp.status_code, 403)

    def do_refine(self):
        resp = self.cl.post(self.url, content_type='application/json', data={'dsid': self.ds.pk})
        self.assertEqual(resp.status_code, 200)
        j = jm.Job.objects.last()
        self.assertEqual(j.funcname, 'refine_mzmls')
        exp_kw = {'dset_id': self.ds.pk, 'wfv_id': settings.MZREFINER_NXFWFV_ID,
                'dbfn_id': settings.MZREFINER_FADB_ID, 'dstshare_id': self.ssmzml.pk,
                'qtype': self.ds.quantdataset.quanttype.shortname}
        for k, val in exp_kw.items():
            self.assertEqual(j.kwargs[k], val)

    def test_refine_mzml(self):
        am.MzmlFile.objects.create(sfile=self.qesf, pwiz=self.pw)
        self.do_refine()
        self.do_refine()
        self.assertEqual(jm.Job.objects.filter(funcname='move_dset_servershare',
            kwargs__dset_id=self.ds.pk).count(), 0)

    def test_with_filemove(self):
        # Create new dataset on old storage proj that can be mock-"moved"
        # Delete afterwards so the count job tests dont go bad between tests
        moverun = dm.RunName.objects.create(name=self.id(), experiment=self.oldexp)
        self.ds.storageshare = self.ssoldstorage
        self.ds.runname = moverun
        self.ds.save()
        am.MzmlFile.objects.create(sfile=self.qesf, pwiz=self.pw)
        self.do_refine()
        self.assertEqual(jm.Job.objects.filter(funcname='move_dset_servershare',
            kwargs__dset_id=self.ds.pk).count(), 1)
        moverun.delete()
