from datetime import datetime, timedelta

from django.utils import timezone
from django.db.models import Max

from kantele.tests import BaseTest
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
        self.pfn2, _ = am.FileParam.objects.get_or_create(name='fp1', nfparam='--fp2', filetype=self.ft2, help='helppi')
        self.txtraw, _ = rm.RawFile.objects.get_or_create(name='txtfn', producer=self.anaprod,
                source_md5='txtraw_fakemd5', size=1234, date=timezone.now(), claimed=False)
        self.txtsf, _ = rm.StoredFile.objects.update_or_create(rawfile=self.txtraw,
                md5=self.txtraw.source_md5, defaults={'filename': self.txtraw.name,
                    'servershare': self.sstmp, 'path': '', 'checked': True, 'filetype': self.ft2})

        c_ch = am.PsetComponent.ComponentChoices
        am.PsetComponent.objects.get_or_create(pset=self.pset, component=c_ch.INPUTDEF, value=['plate', 2, 3])
        am.PsetComponent.objects.get_or_create(pset=self.pset, component=c_ch.ISOQUANT)
        am.PsetComponent.objects.get_or_create(pset=self.pset, component=c_ch.ISOQUANT_SAMPLETABLE)
        am.PsetComponent.objects.get_or_create(pset=self.pset, component=c_ch.PREFRAC, value='.*fr([0-9]+).*mzML$')
        am.PsetParam.objects.get_or_create(pset=self.pset, param=self.param1)
        am.PsetParam.objects.get_or_create(pset=self.pset, param=self.param2)
        am.PsetParam.objects.get_or_create(pset=self.pset, param=self.param3)
        am.PsetMultiFileParam.objects.get_or_create(pset=self.pset, param=self.pfn1)
        am.PsetFileParam.objects.get_or_create(pset=self.pset, param=self.pfn2, allow_resultfiles=True)

        self.nfw, _ = am.NextflowWorkflowRepo.objects.get_or_create(description='a wf', repo='gh/wf')
        self.nfwf, _ = am.NextflowWfVersionParamset.objects.get_or_create(update='an update', commit='abc123',
                filename='main.nf', profiles=[], nfworkflow=self.nfw, paramset=self.pset, nfversion='22', active=True)
        self.wftype = am.UserWorkflow.WFTypeChoices.STD
        self.wf, _ = am.UserWorkflow.objects.get_or_create(name='testwf', wftype=self.wftype, public=True)
        self.wf.nfwfversionparamsets.add(self.nfwf)
        # Create analysis for isoquant:
        self.ana, _ = am.Analysis.objects.get_or_create(user=self.user, name='testana_iso', storage_dir='testdir_iso')
        am.DatasetAnalysis.objects.get_or_create(analysis=self.ana, dataset=self.ds)
        anajob, _ = jm.Job.objects.get_or_create(funcname='testjob', kwargs={}, state='done',
                timestamp=timezone.now())
        self.nfs, _ = am.NextflowSearch.objects.get_or_create(analysis=self.ana, nfwfversionparamset=self.nfwf,
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

        # Create analysis for LF
        self.analf, _ = am.Analysis.objects.get_or_create(user=self.user, name='testana_lf', storage_dir='testdirlf')
        am.DatasetAnalysis.objects.get_or_create(analysis=self.analf, dataset=self.oldds)
        anajoblf, _ = jm.Job.objects.get_or_create(funcname='testjob', kwargs={}, state='done',
                timestamp=timezone.now())
        self.nfslf, _ = am.NextflowSearch.objects.get_or_create(analysis=self.analf, nfwfversionparamset=self.nfwf,
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


class AnalysisIsobaric(AnalysisTest):
    '''For preloaded isobaric analysis (base or new) we load setnames and isoquant'''

    def setUp(self):
        super().setUp()
        self.anaset, _ = am.AnalysisSetname.objects.get_or_create(analysis=self.ana, setname='set1')
        self.ads1, _ = am.AnalysisDatasetSetname.objects.get_or_create(analysis=self.ana,
                dataset=self.ds, setname=self.anaset, regex='hej')
        self.adsif = am.AnalysisDSInputFile.objects.create(analysis=self.ana, sfile=self.f3sfmz, analysisdset=self.ads1)
        self.isoqvals = {'denoms': [self.qch.pk], 'sweep': False, 'report_intensity': False}
        am.AnalysisIsoquant.objects.get_or_create(analysis=self.ana, setname=self.anaset,
                value=self.isoqvals)
        self.samples, _ = am.AnalysisSampletable.objects.get_or_create(analysis=self.ana,
                samples=[[self.qch.name, self.anaset.setname, self.projsam1.sample, 'thegroup']])


class AnalysisLabelfreeSamples(AnalysisTest):
    '''For preloaded LF analysis (base or new) we load file/sample annotations'''

    def setUp(self):
        super().setUp()
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
                #'mzmldef': self.mzmldef.mzmldef,
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
                    'ana': f'{self.wftype.name}_{self.ana.name}',
                    'date': datetime.strftime(self.ana.date, '%Y-%m-%d')}],
                'datasets': {f'{self.ds.pk}': {'frregex': f'{self.ads1.regex}',
                    'setname': f'{self.ads1.setname.setname}', 'filesaresets': False,
                    'files': {}, 'picked_ftype': f'mzML (pwiz {self.f3sfmz.mzmlfile.pwiz.version_description})'}},
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
                #'mzmldef': self.mzmldef.mzmldef,
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
                    'picked_ftype': f'mzML (pwiz {self.f3sfmz.mzmlfile.pwiz.version_description})',
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

    def test_diff_dsets_no_mzmlfile(self):
        '''Base analysis has a single dset attached, this one has two, so we will
        not have dsets_identical and thus we will deliver resultfiles
        '''
        url = f'{self.url}{self.nfwf.pk}/{self.analf.pk}/'
        resp = self.cl.get(url, data={'dsids': f'{self.oldds.pk},{self.ds.pk}', 'added_ana_ids': ''})
        self.assertEqual(resp.status_code, 200)
        rj = resp.json()
        checkjson = {'base_analysis': {'analysis_id': self.analf.pk, 'dsets_identical': False,
                #'mzmldef': self.mzmldeflf.mzmldef,
                'flags': [self.param1.pk],
                'multicheck': [f'{self.param2.pk}___{self.anamcparam.value[0]}'],
                'inputparams': {f'{self.param3.pk}': self.ananormparam.value},
                'multifileparams': {f'{self.pfn1.pk}': {'0': self.tmpsf.pk}},
                'fileparams': {f'{self.pfn2.pk}': self.txtsf.pk},
                'isoquants': {},
                },
                'resultfiles': [{'id': self.resultfnlf.sfile.pk, 'fn': self.resultfnlf.sfile.filename,
                    'ana': f'{self.wftype.name}_{self.analf.name}',
                    'date': datetime.strftime(self.ana.date, '%Y-%m-%d')}],
                'datasets': {f'{self.oldds.pk}': {'filesaresets': True,
                    'picked_ftype': self.afs2.sfile.filetype.name,
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
        
#        # Non-existing dataset FIXME
#        maxds = dm.Dataset.objects.aggregate(Max('pk'))['pk__max']
#        resp = self.cl.get(f'{self.url}', data={'dsids': f'{maxds + 10}', 'anid': 0})
#        self.assertEqual(resp.status_code, 200)
#        self.assertEqual(resp.json()['errmsg'], ['Some datasets could not be found, they may not exist'])

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
        const dbwfs = JSON.parse(document.getElementById('allwfs').textContent);
        const allwfs = dbwfs.wfs;
        const wforder = dbwfs.order;
        const ds_errors = [


        ];
        </script>
        '''
        self.assertInHTML(html_dsids, resphtml)
        self.isoqvals = {'denoms': [self.qch.pk], 'sweep': False, 'report_intensity': False}
        html_ana = f'''<script id="analysis_data" type="application/json">
        {{"analysis_id": {self.ana.pk}, "editable": false, "wfversion_id": {self.nfwf.pk}, "wfid": {self.wf.pk}, "analysisname": "{self.ana.name}", "flags": [{self.param1.pk}], "multicheck": ["{self.param2.pk}___{self.anamcparam.value[0]}"], "inputparams": {{"{self.param3.pk}": {self.ananormparam.value}}}, "multifileparams": {{"{self.pfn1.pk}": {{"0": {self.tmpsf.pk}}}}}, "fileparams": {{"{self.pfn2.pk}": {self.txtsf.pk}}}, "isoquants": {{"{self.anaset.setname}": {{"chemistry": "{self.ds.quantdataset.quanttype.shortname}", "channels": {{"{self.qch.name}": ["{self.projsam1.sample}", {self.qch.pk}]}}, "samplegroups": {{"{self.samples.samples[0][0]}": "{self.samples.samples[0][3]}"}}, "denoms": [{self.qch.pk}], "report_intensity": false, "sweep": false}}}}, "added_results": {{}}, "base_analysis": false}}
        </script>
        '''
        self.assertInHTML(html_ana, resphtml)


class TestGetDatasets(AnalysisTest):
    url = '/analysis/dsets/'

    def test_bad_req(self):
        resp = self.cl.post(f'{self.url}{self.nfwf.pk}/')
        self.assertEqual(resp.status_code, 405)
        resp = self.cl.get(f'{self.url}{self.nfwf.pk}/')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(['Something wrong when asking datasets, contact admin'], resp.json()['errmsg'])

    def test_new_ok(self):
        '''New analysis with datasets, try both LF and isobaric'''
        resp = self.cl.get(f'{self.url}{self.nfwf.pk}/', data={'dsids': f'{self.ds.pk}', 'anid': 0})
        self.assertEqual(resp.status_code, 200)
        dsname = f'{self.ds.runname.experiment.project.name} / {self.ds.runname.experiment.name} / {self.ds.runname.name}'
        checkjson = {
                'dsets': {},
                'error': False,
                'errmsg': [],
                }
        self.assertJSONEqual(resp.content.decode('utf-8'), checkjson)

    def test_with_saved_analysis(self):
        self.fail()

    def test_error(self):
        '''This test is on single dataset which will fail, in various ways'''
        # No quant details
        fn = 'noqt_fn'
        path = 'noqt_stor'
        raw = rm.RawFile.objects.create(name=fn, producer=self.prod,
                source_md5='noqt_fakemd5',
                size=100, date=timezone.now(), claimed=True)
        sf, _ = rm.StoredFile.objects.update_or_create(rawfile=raw, filename=fn,
                    md5=raw.source_md5, filetype=self.ft,
                    defaults={'servershare': self.ssnewstore, 'path': path, 'checked': True})
        newrun, _ = dm.RunName.objects.get_or_create(experiment=self.ds.runname.experiment,
                name='noqt_ds')
        newds, _ = dm.Dataset.objects.get_or_create(runname=newrun, datatype=self.ds.datatype, 
                storage_loc=path, storageshare=self.ds.storageshare,
                defaults={'date': timezone.now()})
        dsr, _ = dm.DatasetRawFile.objects.get_or_create(dataset=newds, rawfile=raw)
        dm.DatasetOwner.objects.get_or_create(dataset=newds, user=self.user)
        resp = self.cl.get(f'{self.url}{self.nfwf.pk}/', data={'dsids': f'{newds.pk}', 'anid': 0})
        self.assertEqual(resp.status_code, 400)
        dsname = f'{self.ds.runname.experiment.project.name} / {self.ds.runname.experiment.name} / {newrun.name}'
        self.assertIn(f'File(s) or channels in dataset {dsname} do not have sample annotations, '
                'please edit the dataset first', resp.json()['errmsg'])


class TestGetWorkflowVersionDetails(AnalysisTest):
    url = '/analysis/workflow/'

    def test_bad_req(self):
        resp = self.cl.post(self.url)
        self.assertEqual(resp.status_code, 405)
        resp = self.cl.get(self.url)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'Something is wrong, contact admin')
        maxpk = am.NextflowWorkflowRepo.objects.aggregate(Max('pk'))['pk__max']
        resp = self.cl.get(self.url, data={'wfvid': maxpk + 10, 'dsids': f'{self.ds.pk}'})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()['error'], 'Could not find workflow')

    def test_ok(self):
        # Add some usr file to make it show up in the dropdown, and make sure the other
        # userfile is not (wrong filetype)
        usrfraw_ft, _ = rm.RawFile.objects.update_or_create(name='userfile_right_ft', 
                producer=self.prod, source_md5='usrf_rightft_md5',
                size=100, defaults={'claimed': False, 'date': timezone.now()})
        sfusr_ft, _ = rm.StoredFile.objects.update_or_create(rawfile=usrfraw_ft,
                md5=usrfraw_ft.source_md5, filetype=self.ft2, defaults={'filename': usrfraw_ft.name,
                    'servershare': self.sstmp, 'path': '', 'checked': True})
        utoken_ft, _ = rm.UploadToken.objects.update_or_create(user=self.user, token='token_ft',
                expired=False, producer=self.prod, filetype=sfusr_ft.filetype, defaults={
                    'expires': timezone.now() + timedelta(1)})
        userfile_ft, _ = rm.UserFile.objects.get_or_create(sfile=sfusr_ft,
                description='This is a userfile', upload=utoken_ft)
        resp = self.cl.get(self.url, data={'wfvid': self.nfwf.pk, 'dsids': f'{self.ds.pk}'})
        self.assertEqual(resp.status_code, 200)
        allcomponents = {x.value: x for x in am.PsetComponent.ComponentChoices}
        checkjson = {'wf': {
            'components': {allcomponents[x.component].name: x.value 
                for x in  self.nfwf.paramset.psetcomponent_set.all()},
            'flags': [{'nf': x.param.nfparam, 'name': x.param.name, 'id': x.param.pk,
                'help': x.param.help or False}
                for x in self.nfwf.paramset.psetparam_set.filter(param__ptype='flag')],
            'numparams': [{'nf': x.param.nfparam, 'name': x.param.name, 'id': x.param.pk,
                'help': x.param.help or False}
                for x in self.nfwf.paramset.psetparam_set.filter(param__ptype='number')],
            'textparams': [{'nf': x.param.nfparam, 'name': x.param.name, 'id': x.param.pk,
                'help': x.param.help or False}
                for x in self.nfwf.paramset.psetparam_set.filter(param__ptype='text')],
            'multicheck': [{'nf': x.param.nfparam, 'name': x.param.name, 'id': x.param.pk,
                'opts': {f'{po.pk}': po.name for po in x.param.paramoption_set.all()},
                'help': x.param.help or False}
                for x in self.nfwf.paramset.psetparam_set.filter(param__ptype='multi')],
            'fileparams': [{'nf': x.param.nfparam, 'name': x.param.name, 'id': x.param.pk,
                'ftype': x.param.filetype_id, 'allow_resultfile': x.allow_resultfiles,
                'help': x.param.help or False}
                for x in self.nfwf.paramset.psetfileparam_set.all()],
            'multifileparams': [{'nf': x.param.nfparam, 'name': x.param.name, 'id': x.param.pk,
                'ftype': x.param.filetype_id, 'allow_resultfile': x.allow_resultfiles,
                'help': x.param.help or False}
                for x in self.nfwf.paramset.psetmultifileparam_set.all()],
            'libfiles': {f'{ft}': [{'id': x.sfile.id, 'desc': x.description,
                'name': x.sfile.filename} for x in [self.lf, userfile_ft]
                if x.sfile.filetype_id == ft]
                for ft in [self.lf.sfile.filetype_id, sfusr_ft.filetype_id]},
            'prev_resultfiles': [{'ana': f'{self.wftype.name}_{self.ana.name}',
                'date': datetime.strftime(self.ana.date, '%Y-%m-%d'), 'id': self.resultfn.sfile_id,
                'fn': self.resultfn.sfile.filename}],
            }}
        self.assertJSONEqual(resp.content.decode('utf-8'), checkjson)


class TestStoreAnalysis(AnalysisTest):
    url = '/analysis/store/'

    def test_bad_req(self):
        resp = self.cl.get(self.url)
        self.assertEqual(resp.status_code, 405)
        resp = self.cl.post(self.url)
        self.assertEqual(resp.status_code, 400)
        resp = self.cl.post(self.url, content_type='application/json', data={})
        self.assertEqual(resp.status_code, 400)

    def test_new_analysis(self):
        quant = self.ds.quantdataset.quanttype
        params = {'flags': {self.param1.pk: True}, 'inputparams': {self.param3.pk: 42}, 
                'multicheck': {self.param2.pk: [self.popt1.pk]}}
        postdata = {'dsids': [f'{self.ds.pk}'],
            'analysis_id': False,
            'infiles': {self.f3sfmz.pk: 1},
            'picked_ftypes': {self.ds.pk: f'mzML (pwiz {self.f3sfmz.mzmlfile.pwiz.version_description})'},
            'nfwfvid': self.nfwf.pk,
            'dssetnames': {self.ds.pk: 'setA'},
            'components': {'ISOQUANT_SAMPLETABLE': {'hello': 'yes'},
                'INPUTDEF': 'a',
                'ISOQUANT': {'setA': {'chemistry': quant.shortname,
                    'denoms': {x.channel.name: [f'{x}_sample', x.channel.id] for x in quant.quanttypechannel_set.all()},
                    'report_intensity': False,
                    'sweep': False,
                    }},
                },
            'analysisname': 'Test new analysis',
            'frregex': {f'{self.ds.pk}': 'fr_find'},
            'fnsetnames': {},
            'params': params,
            'singlefiles': {self.pfn2.pk: self.sflib.pk},
            'multifiles': {self.pfn1.pk: [self.sfusr.pk]},
            # FIXME use self.ana here
            'base_analysis': {'isComplement': False,
                'dsets_identical': False,
                'selected': False,
                'typedname': '',
                'fetched': {},
                'resultfiles': [],
                },
            'wfid': self.wf.pk,
            }
        resp = self.cl.post(self.url, content_type='application/json', data=postdata)
        timestamp = datetime.strftime(datetime.now(), '%Y%m%d_')
        self.assertEqual(resp.status_code, 200)
        ana = am.Analysis.objects.last()
        #self.assertEqual(ana.analysismzmldef.mzmldef, postdata['components']['mzmldef'])
        self.assertEqual(ana.analysissampletable.samples, {'hello': 'yes'})
        for adsif in ana.analysisdsinputfile_set.all():
            self.assertEqual(adsif.analysisdset.dataset_id, self.ds.pk)
            self.assertEqual(adsif.analysisdset.setname.setname, postdata['dssetnames'][self.ds.pk])
            self.assertEqual(adsif.analysisdset.regex, postdata['frregex'][f'{self.ds.pk}'])
        for ap in ana.analysisparam_set.all():
            pt = {'multi': 'multicheck', 'text': 'inputparams', 'number': 'inputparams',
                    'flag': 'flags'}[ap.param.ptype]
            self.assertEqual(ap.value, params[pt][ap.param_id])
        self.assertEqual(ana.name, postdata['analysisname'])
        fullname = f'{ana.pk}_{self.wftype.name}_{ana.name}_{timestamp}'
        # This test flakes if executed right at midnight due to timestamp in assert string
        self.assertEqual(ana.storage_dir[:-5], f'{ana.user.username}/{fullname}')
        checkjson = {'error': False, 'analysis_id': ana.pk}
        self.assertJSONEqual(resp.content.decode('utf-8'), checkjson)

    # FIXME existing ana

    # FIXME fail tests
