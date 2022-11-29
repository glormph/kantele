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
        ps = am.ParameterSet.objects.create(name='')
        nfw = am.NextflowWorkflow.objects.create(description='', repo='')
        self.nfwv = am.NextflowWfVersion.objects.create(update='', commit='', filename='', nfworkflow=nfw,
                paramset=ps, kanteleanalysis_version=1, nfversion='')
        self.pw = am.Proteowizard.objects.create(version_description='', container_version='', nf_version=self.nfwv, is_docker=True)
        # Stored files input
        self.ssmzml = rm.ServerShare.objects.create(name=settings.MZMLINSHARENAME, server=self.newfserver,
                share='/home/mzmls')
        self.ft = rm.StoredFileType.objects.create(name='Thermo raw', filetype='raw')
        self.prodqe = rm.Producer.objects.create(name='prod1', client_id='abcdefg', shortname='p1')
        self.prodtims = rm.Producer.objects.create(name='prod2', client_id='abcdefg', shortname='p2')
        self.tims = rm.MSInstrumentType.objects.create(name='timstof')
        self.qe = rm.MSInstrumentType.objects.create(name='qe')
        instqe = rm.MSInstrument.objects.create(producer=self.prodqe, instrumenttype=self.qe,
                filetype=self.ft)
        insttims = rm.MSInstrument.objects.create(producer=self.prodtims, instrumenttype=self.tims,
                filetype=self.ft)
        own1 = dm.DatasetOwner.objects.create(dataset=self.ds, user=self.user)
        self.oldraw = rm.RawFile.objects.create(name='file1', producer=self.prodqe,
                source_md5='52416cc60390c66e875ee6ed8e03103a',
                size=100, date=timezone.now(), claimed=True)
        self.sf = rm.StoredFile.objects.create(rawfile=self.oldraw, filename=self.oldraw.name, servershare=self.ds.storageshare,
                path=self.storloc, md5=self.oldraw.source_md5, checked=True, filetype=self.ft)
        self.timsraw = rm.RawFile.objects.create(name='file2', producer=self.prodtims,
                source_md5='timsmd4',
                size=100, date=timezone.now(), claimed=True)
        dm.DatasetRawFile.objects.create(dataset=self.ds, rawfile=self.oldraw)


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
        dm.DatasetRawFile.objects.create(dataset=self.ds, rawfile=self.timsraw)
        resp = self.cl.post(self.url, content_type='application/json', data={'pwiz_id': self.pw.pk,
            'dsid': self.ds.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('contains data from multiple instrument types', resp.json()['error'])
    
    def test_existing_mzmls(self):
        am.MzmlFile.objects.create(sfile=self.sf, pwiz=self.pw)
        resp = self.cl.post(self.url, content_type='application/json', data={'pwiz_id': self.pw.pk,
            'dsid': self.ds.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('already has existing mzML files of that proteowizard', resp.json()['error'])

    def test_other_pwiz(self):
        newpw = am.Proteowizard.objects.create(version_description='newer', container_version='', nf_version=self.nfwv)
        am.MzmlFile.objects.create(sfile=self.sf, pwiz=newpw)
        resp = self.cl.post(self.url, content_type='application/json', data={'pwiz_id': self.pw.pk,
            'dsid': self.ds.pk})
        self.assertEqual(resp.status_code, 200)
        j = jm.Job.objects.last()
        self.assertEqual(j.funcname, 'convert_dataset_mzml')
        exp_kw  = {'options': [], 'filters': ['"peakPicking true 2"', '"precursorRefine"'], 
                'dset_id': self.ds.pk, 'pwiz_id': self.pw.pk}
        for k, val in exp_kw.items():
            self.assertEqual(j.kwargs[k], val)
        self.sf.refresh_from_db()
        self.assertTrue(self.sf.deleted)
        self.assertEqual(jm.Job.objects.filter(funcname='move_dset_servershare').count(), 0)

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
        self.assertEqual(jm.Job.objects.filter(funcname='move_dset_servershare').count(), 0)

    def test_create_mzml_tims(self):
        self.oldraw.producer = self.prodtims
        self.oldraw.save()
        postdata = {'pwiz_id': self.pw.pk, 'dsid': self.ds.pk}
        resp = self.cl.post(self.url, content_type='application/json', data=postdata)
        self.assertEqual(resp.status_code, 200)
        j = jm.Job.objects.last()
        self.assertEqual(j.funcname, 'convert_dataset_mzml')
        exp_kw  = {'options': ['combineIonMobilitySpectra'], 'filters': ['"peakPicking true 2"', '"precursorRefine"', '"scanSumming precursorTol=0.02 scanTimeTol=10 ionMobilityTol=0.1"'], 
                'dstshare_id': self.ssmzml.pk, 'dset_id': self.ds.pk, 'pwiz_id': self.pw.pk}
        for k, val in exp_kw.items():
            self.assertEqual(j.kwargs[k], val)
        self.assertEqual(jm.Job.objects.filter(funcname='move_dset_servershare').count(), 0)

    def test_with_filemove(self):
        self.ds.storageshare = self.ssoldstorage
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
        self.assertEqual(jm.Job.objects.filter(funcname='move_dset_servershare').count(), 1)


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
        refinedsf = rm.StoredFile.objects.create(rawfile=self.oldraw, filename=self.oldraw.name, servershare=self.ds.storageshare,
                path=self.storloc, md5='refined_md5', checked=True, filetype=self.ft)
        am.MzmlFile.objects.create(sfile=refinedsf, pwiz=self.pw, refined=True)
        am.MzmlFile.objects.create(sfile=self.sf, pwiz=self.pw)
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
        am.MzmlFile.objects.create(sfile=self.sf, pwiz=self.pw)
        self.do_refine()
        self.do_refine()
        self.assertEqual(jm.Job.objects.filter(funcname='move_dset_servershare').count(), 0)

    def test_with_filemove(self):
        self.ds.storageshare = self.ssoldstorage
        self.ds.save()
        am.MzmlFile.objects.create(sfile=self.sf, pwiz=self.pw)
        self.do_refine()
        self.assertEqual(jm.Job.objects.filter(funcname='move_dset_servershare').count(), 1)
