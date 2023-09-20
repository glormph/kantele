from datetime import datetime

from django.utils import timezone

from kantele.tests import BaseTest, BaseIntegrationTest
from analysis import models as am
from rawstatus import models as rm
from jobs import models as jm
from datasets import models as dm


class AnalysisTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.pset, _ = am.ParameterSet.objects.get_or_create(name='ps1')
        self.param1, _ = am.Param.objects.get_or_create(name='a flag', nfparam='--flag', ptype='flag', help='flag help')
        self.param2, _ = am.Param.objects.get_or_create(name='a chbox', nfparam='--multi', ptype='multi', help='help')
        self.param3, _ = am.Param.objects.get_or_create(name='a num', nfparam='--num', ptype='number', help='help')
        self.popt1, _ = am.ParamOption.objects.get_or_create(param=self.param2, name='opt 1', value='nr1')
        popt2, _ = am.ParamOption.objects.get_or_create(param=self.param2, name='opt 2', value='nr2')
        self.pfn1, _ = am.FileParam.objects.get_or_create(name='fp1', nfparam='--fp1', filetype=self.ft, help='help')

        self.ft2, _ = rm.StoredFileType.objects.get_or_create(name='result ft', filetype='txt')
        self.pfn2, _ = am.FileParam.objects.get_or_create(name='fp1', nfparam='--fp1', filetype=self.ft2, help='helppi')
        self.txtraw, _ = rm.RawFile.objects.get_or_create(name='txtfn', producer=self.anaprod,
                source_md5='txtraw_fakemd5', size=1234, date=timezone.now(), claimed=False)
        self.txtsf, _ = rm.StoredFile.objects.update_or_create(rawfile=self.txtraw,
                md5=self.txtraw.source_md5, defaults={'filename': self.txtraw.name,
                    'servershare': self.sstmp, 'path': '', 'checked': True, 'filetype': self.ft2})

        wfc, _ = am.WFInputComponent.objects.get_or_create(name='mzmldef', value=[1,2,3])
        am.PsetComponent.objects.get_or_create(pset=self.pset, component=wfc)
        am.PsetParam.objects.get_or_create(pset=self.pset, param=self.param1)
        am.PsetParam.objects.get_or_create(pset=self.pset, param=self.param2)
        am.PsetParam.objects.get_or_create(pset=self.pset, param=self.param3)
        am.PsetMultiFileParam.objects.get_or_create(pset=self.pset, param=self.pfn1)
        am.PsetFileParam.objects.get_or_create(pset=self.pset, param=self.pfn2, allow_resultfiles=True)

        wft, _ = am.WorkflowType.objects.get_or_create(name='wftype1')
        self.nfw, _ = am.NextflowWorkflow.objects.get_or_create(description='a wf', repo='gh/wf')
        self.wf, _ = am.Workflow.objects.get_or_create(name='testwf', shortname=wft,
                nfworkflow=self.nfw, public=True)
        self.nfwf, _ = am.NextflowWfVersion.objects.get_or_create(update='an update', commit='abc123',
                filename='main.nf', profiles=[], nfworkflow=self.nfw, paramset=self.pset,
                kanteleanalysis_version=1, # FIXME remove
                nfversion='22')
        # Create analysis for isoquant:
        self.ana, _ = am.Analysis.objects.get_or_create(user=self.user, name='testana_iso', storage_dir='testdir_iso')
        am.DatasetSearch.objects.get_or_create(analysis=self.ana, dataset=self.ds)
        anajob, _ = jm.Job.objects.get_or_create(funcname='testjob', kwargs={}, state='done',
                timestamp=timezone.now())
        self.nfs, _ = am.NextflowSearch.objects.get_or_create(analysis=self.ana, nfworkflow=self.nfwf,
                workflow=self.wf, token='tok123', job=anajob)
        am.AnalysisParam.objects.get_or_create(analysis=self.ana, param=self.param1, value=True)
        self.anamcparam, _ = am.AnalysisParam.objects.get_or_create(analysis=self.ana, param=self.param2,
                value=[self.popt1.value])
        self.ananormparam, _ = am.AnalysisParam.objects.get_or_create(analysis=self.ana,
                param=self.param3, value=3)
        self.anamfparam, _ = am.AnalysisFileParam.objects.get_or_create(analysis=self.ana,
                param=self.pfn1, sfile=self.tmpsf)
        self.anafparam, _ = am.AnalysisFileParam.objects.get_or_create(analysis=self.ana,
                param=self.pfn2, sfile=self.txtsf)
        self.resultfn, _ = am.AnalysisResultFile.objects.get_or_create(analysis=self.ana,
                sfile=self.anasfile)
        self.mzmldef, _ = am.AnalysisMzmldef.objects.get_or_create(analysis=self.ana, mzmldef='testmzd')

        # Create analysis for LF
        self.analf, _ = am.Analysis.objects.get_or_create(user=self.user, name='testana_lf', storage_dir='testdirlf')
        am.DatasetSearch.objects.get_or_create(analysis=self.analf, dataset=self.oldds)
        anajoblf, _ = jm.Job.objects.get_or_create(funcname='testjob', kwargs={}, state='done',
                timestamp=timezone.now())
        self.nfslf, _ = am.NextflowSearch.objects.get_or_create(analysis=self.analf, nfworkflow=self.nfwf,
                workflow=self.wf, token='tok12344', job=anajoblf)

        am.AnalysisParam.objects.get_or_create(analysis=self.analf, param=self.param1, value=True)
        self.anamcparamlf, _ = am.AnalysisParam.objects.get_or_create(analysis=self.analf, param=self.param2,
                value=[self.popt1.value])
        self.ananormparamlf, _ = am.AnalysisParam.objects.get_or_create(analysis=self.analf,
                param=self.param3, value=3)
        self.anamfparamlf, _ = am.AnalysisFileParam.objects.get_or_create(analysis=self.analf,
                param=self.pfn1, sfile=self.tmpsf)
        self.anafparamlf, _ = am.AnalysisFileParam.objects.get_or_create(analysis=self.analf,
                param=self.pfn2, sfile=self.txtsf)
        self.resultfnlf, _ = am.AnalysisResultFile.objects.get_or_create(analysis=self.analf,
                sfile=self.anasfile2)
        self.mzmldeflf, _ = am.AnalysisMzmldef.objects.get_or_create(analysis=self.analf, mzmldef='lfmz')


class AnalysisIsobaric(AnalysisTest):
    '''For preloaded isobaric analysis (base or new) we load setnames and isoquant'''

    def setUp(self):
        super().setUp()
        self.anaset, _ = am.AnalysisSetname.objects.get_or_create(analysis=self.ana, setname='set1')
        self.ads1, _ = am.AnalysisDatasetSetname.objects.get_or_create(analysis=self.ana,
                dataset=self.ds, setname=self.anaset, regex='hej')
        self.qcs, _  = dm.QuantChannelSample.objects.get_or_create(dataset=self.ds, channel=self.qtch,
                projsample=self.projsam1)
        self.isoqvals = {'denoms': [self.qch.pk], 'sweep': False, 'report_intensity': False}
        am.AnalysisIsoquant.objects.get_or_create(analysis=self.ana, setname=self.anaset,
                value=self.isoqvals)
        self.samples, _ = am.AnalysisSampletable.objects.get_or_create(analysis=self.ana,
                samples=[[self.qch.name, self.anaset.setname, self.projsam1.sample, 'thegroup']])


class AnalysisLabelfreeSamples(AnalysisTest):
    '''For preloaded LF analysis (base or new) we load file/sample annotations'''

    def setUp(self):
        super().setUp()
        dm.QuantSampleFile.objects.get_or_create(rawfile=self.olddsr, projsample=self.projsam2)
        self.afs2, _ = am.AnalysisFileSample.objects.get_or_create(analysis=self.analf, sample='newname2', sfile=self.oldsf)


class TestNewAnalysis(BaseTest):
    url = '/analysis/new/'

    def test_ok(self):
        resp = self.cl.get(self.url, data={'dsids': self.ds.pk})
        self.assertEqual(resp.status_code, 200)

    def test_post(self):
        resp = self.cl.post(self.url)
        self.assertEqual(resp.status_code, 405)


class LoadBaseAnaTestIso(AnalysisIsobaric):
    url = '/analysis/baseanalysis/load/'

    def test_diff_dsets(self):
        '''Base analysis requested has a single dataset connected, this one asks for two, so we 
        need to get resultfiles from the base analysis as they will not be included in the 
        dropdowns already (any resultfile from an analysis with identical dsets as input will be)'''
        url = f'{self.url}{self.nfwf.pk}/{self.ana.pk}/'
        resp = self.cl.get(url, data={'dsids': f'{self.ds.pk},{self.oldds.pk}', 'added_ana_ids': ''})
        self.assertEqual(resp.status_code, 200)
        rj = resp.json()
        checkjson = {'base_analysis': {'analysis_id': self.ana.pk, 'dsets_identical': False,
                'mzmldef': self.mzmldef.mzmldef,
                'flags': [self.param1.pk],
                'multicheck': [f'{self.param2.pk}___{self.anamcparam.value[0]}'],
                'inputparams': {f'{self.param3.pk}': self.ananormparam.value},
                'multifileparams': {f'{self.pfn1.pk}': {'0': self.tmpsf.pk}},
                'fileparams': {f'{self.pfn2.pk}': self.txtsf.pk},
                'isoquants': {self.ads1.setname.setname: {**self.isoqvals,
                    'chemistry': self.ds.quantdataset.quanttype.shortname,
                    'channels': {self.qch.name: [self.projsam1.sample, self.qch.pk]},
                    'samplegroups': {self.samples.samples[0][0]: self.samples.samples[0][3]}}},
                },
                'resultfiles': [{'id': self.resultfn.sfile.pk, 'fn': self.resultfnlf.sfile.filename,
                    'ana': f'{self.nfs.workflow.shortname}_{self.ana.name}',
                    'date': datetime.strftime(self.ana.date, '%Y-%m-%d')}],
                'datasets': {f'{self.ds.pk}': {'frregex': f'{self.ads1.regex}',
                    'setname': f'{self.ads1.setname.setname}', 'filesaresets': False,
                    'files': {}}}
                }
        self.assertJSONEqual(resp.content.decode('utf-8'), checkjson)

    def test_same_dsets(self):
        '''Base analysis requested has a single dset connected, this analysis too, so we need
        output which has no base analysis resultfiles as they will already be loaded as part
        of the other same analysis
        '''
        url = f'{self.url}{self.nfwf.pk}/{self.ana.pk}/'
        resp = self.cl.get(url, data={'dsids': self.ds.pk, 'added_ana_ids': ''})
        self.assertEqual(resp.status_code, 200)
        rj = resp.json()
        checkjson = {'base_analysis': {'analysis_id': self.ana.pk, 'dsets_identical': True,
                'mzmldef': self.mzmldef.mzmldef,
                'flags': [self.param1.pk],
                'multicheck': [f'{self.param2.pk}___{self.anamcparam.value[0]}'],
                'inputparams': {f'{self.param3.pk}': self.ananormparam.value},
                'multifileparams': {f'{self.pfn1.pk}': {'0': self.tmpsf.pk}},
                'fileparams': {f'{self.pfn2.pk}': self.txtsf.pk},
                'isoquants': {self.ads1.setname.setname: {**self.isoqvals,
                    'chemistry': self.ds.quantdataset.quanttype.shortname,
                    'channels': {self.qch.name: [self.projsam1.sample, self.qch.pk]},
                    'samplegroups': {self.samples.samples[0][0]: self.samples.samples[0][3]}}},
                },
                'resultfiles': [],
                'datasets': {f'{self.ds.pk}': {'frregex': f'{self.ads1.regex}',
                    'setname': f'{self.ads1.setname.setname}',
                    'filesaresets': False, 'files': {}},
                    }
                }
        self.assertJSONEqual(resp.content.decode('utf-8'), checkjson)

    def test_no_params_or_post(self):
        url = f'{self.url}1/1/'
        resp = self.cl.get(url)
        self.assertEqual(resp.status_code, 400)
        resp = self.cl.post(url)
        self.assertEqual(resp.status_code, 405)


class LoadBaseAnaTestLF(AnalysisLabelfreeSamples):
    url = '/analysis/baseanalysis/load/'

    def test_diff_dsets(self):
        '''Base analysis has a single dset attached, this one has two, so we will
        not have dsets_identical and thus we will deliver resultfiles
        '''
        url = f'{self.url}{self.nfwf.pk}/{self.analf.pk}/'
        resp = self.cl.get(url, data={'dsids': f'{self.oldds.pk},{self.ds.pk}', 'added_ana_ids': ''})
        self.assertEqual(resp.status_code, 200)
        rj = resp.json()
        checkjson = {'base_analysis': {'analysis_id': self.analf.pk, 'dsets_identical': False,
                'mzmldef': self.mzmldeflf.mzmldef,
                'flags': [self.param1.pk],
                'multicheck': [f'{self.param2.pk}___{self.anamcparam.value[0]}'],
                'inputparams': {f'{self.param3.pk}': self.ananormparam.value},
                'multifileparams': {f'{self.pfn1.pk}': {'0': self.tmpsf.pk}},
                'fileparams': {f'{self.pfn2.pk}': self.txtsf.pk},
                'isoquants': {},
                },
                'resultfiles': [{'id': self.resultfnlf.sfile.pk, 'fn': self.resultfnlf.sfile.filename,
                    'ana': f'{self.nfs.workflow.shortname}_{self.analf.name}',
                    'date': datetime.strftime(self.ana.date, '%Y-%m-%d')}],
                'datasets': {f'{self.oldds.pk}': {'filesaresets': True,
                    'files': {f'{self.afs2.sfile_id}': {'id': self.afs2.sfile_id,
                        'setname': self.afs2.sample}}},
                    },
                }
        self.assertJSONEqual(resp.content.decode('utf-8'), checkjson)


class TestGetAnalysis(AnalysisIsobaric):
    url = '/analysis/'

    # FIXME load_base and get_analysis do the same serialization on the inputs I think,
    # maybe it's worth centralizing that function
    def test_no_params_or_post(self):
        url = f'{self.url}1abc/'
        resp = self.cl.get(url)
        self.assertEqual(resp.status_code, 404)
        url = f'{self.url}1/'
        resp = self.cl.post(url)
        self.assertEqual(resp.status_code, 405)

    def test_ok(self):
        url = f'{self.url}{self.ana.nextflowsearch.pk}/'
        resp = self.cl.get(url)
        self.assertEqual(resp.status_code, 200)
        resphtml = resp.content.decode('utf-8')
        html_dsids = f'''<script>
        let dsids = [
                      
                      "{self.ds.pk}",
                            
                            ];
        let existing_analysis = JSON.parse(document.getElementById('analysis_data').textContent);
        </script>
        '''
        self.assertInHTML(html_dsids, resphtml)
        self.isoqvals = {'denoms': [self.qch.pk], 'sweep': False, 'report_intensity': False}
        html_ana = f'''<script id="analysis_data" type="application/json">
        {{"analysis_id": {self.ana.pk}, "editable": false, "wfversion_id": {self.nfwf.pk}, "wfid": {self.nfw.pk}, "mzmldef": "{self.mzmldef.mzmldef}", "analysisname": "{self.ana.name}", "flags": [{self.param1.pk}], "multicheck": ["{self.param2.pk}___{self.anamcparam.value[0]}"], "inputparams": {{"{self.param3.pk}": {self.ananormparam.value}}}, "multifileparams": {{"{self.pfn1.pk}": {{"0": {self.tmpsf.pk}}}}}, "fileparams": {{"{self.pfn2.pk}": {self.txtsf.pk}}}, "isoquants": {{"{self.anaset.setname}": {{"chemistry": "{self.ds.quantdataset.quanttype.shortname}", "channels": {{"{self.qch.name}": ["{self.projsam1.sample}", {self.qch.pk}]}}, "samplegroups": {{"{self.samples.samples[0][0]}": "{self.samples.samples[0][3]}"}}, "denoms": [{self.qch.pk}], "report_intensity": false, "sweep": false}}}}, "added_results": {{}}, "base_analysis": false}}
        </script>
        '''
        self.assertInHTML(html_ana, resphtml)
