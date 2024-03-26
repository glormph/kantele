from django.db import models
from django.contrib.auth.models import User

from rawstatus import models as filemodels
from datasets import models as dsmodels
from jobs import models as jmodels


class LibraryFile(models.Model):
    description = models.TextField()
    sfile = models.OneToOneField(filemodels.StoredFile, on_delete=models.CASCADE)

    def __str__(self):
        return self.description


class FileParam(models.Model):
    name = models.TextField()
    nfparam = models.TextField()
    filetype = models.ForeignKey(filemodels.StoredFileType, on_delete=models.CASCADE)
    help = models.TextField()

    def __str__(self):
        return self.name


class Param(models.Model):
    class PTypes(models.IntegerChoices):
        FLAG = 1, 'Flag'
        MULTI = 2, 'Multiple choice checkbox'
        TEXT = 3, 'Text'
        NUMBER = 4, 'Numbers, integers, floats'
        SELECT = 5, 'Single choice select'

    name = models.TextField()
    nfparam = models.TextField()
    ptype = models.IntegerField(choices=PTypes.choices)
    visible = models.BooleanField(default=True)
    help = models.TextField()

    def __str__(self):
        return self.name


class ParamOption(models.Model):
    param = models.ForeignKey(Param, on_delete=models.CASCADE)
    name = models.TextField()
    value = models.TextField()

    def __str__(self):
        return '{} - {}'.format(self.param.name, self.name)


class ParameterSet(models.Model):
    name = models.TextField()

    def __str__(self):
        return self.name


class NextflowWorkflowRepo(models.Model):
    description = models.TextField(help_text='Description of workflow')
    repo = models.TextField()
    
    def __str__(self):
        return self.description


class NextflowWfVersionParamset(models.Model):
    update = models.TextField(help_text='Description of workflow update')
    # NB commit cannot be unique, in case of multiple paramsets
    commit = models.CharField(max_length=50)
    filename = models.TextField()
    profiles = models.JSONField(default=list)
    nfworkflow = models.ForeignKey(NextflowWorkflowRepo, on_delete=models.CASCADE)
    paramset = models.ForeignKey(ParameterSet, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now=True)
    nfversion = models.TextField()
    active = models.BooleanField(default=False)
    
    def __str__(self):
        return '{} - {}'.format(self.nfworkflow.description, self.update)


class UserWorkflow(models.Model):

    class WFTypeChoices(models.IntegerChoices):
        STD = 1, 'Quantitative proteomics'
        QC = 2, 'Instrument quality control'
        VARDB = 3, 'Other proteomics, special DB'
        DBGEN = 4, 'Proteogenomics DB generation'
        PISEP = 5, 'pI-separated identification'
        SPEC = 6, 'Special internal'
        LC = 7, 'Labelcheck'

    name = models.TextField()
    wftype = models.IntegerField(choices=WFTypeChoices.choices)
    nfwfversionparamsets = models.ManyToManyField(NextflowWfVersionParamset)
    public = models.BooleanField()

    def __str__(self):
        return self.name


class PsetComponent(models.Model):
    '''Special components for a parameter set. Components are such elements for a workflow
    that require special, non generalized code written for it. They can be in multiple workflows
    but are not as generalized as e.g. parameters'''

    class ComponentChoices(models.IntegerChoices):
        ISOQUANT = 1, 'Isobaric quant summarizing with denominators, median sweep, or intensity'
        INPUTDEF = 2, 'Input file definition of specific type, value eg [path, instrument, sample]'
        ISOQUANT_SAMPLETABLE = 3, 'Sampletable for isobaric quant'
        LABELCHECK_ISO = 4, 'Labelcheck isoquant'
        COMPLEMENT_ANALYSIS = 5, 'MS search complementing earlier run or rerun from PSMs'
        PREFRAC = 6, 'Prefractionated MS data'
        HIRIEF_STRIP_TOLERANCE = 7, 'HiRIEF strip tolerance'
        # DSET_NAMES ?

    pset = models.ForeignKey(ParameterSet, on_delete=models.CASCADE)
    component = models.IntegerField(choices=ComponentChoices.choices)
    value = models.JSONField(default=dict) 
    # JSON in value: if needed eg mzmldef: [path, instrument, set, plate, fr]
    # else {}
    # FIXME future also setnames, sampletables, fractions, etc which is not a param
    # to be included in parameterset
    # prefrac '.*fr([0-9]+).*mzML$'

    def __str__(self):
        return '{} - {}'.format(self.pset.name, self.ComponentChoices(self.component).label)


class PsetFileParam(models.Model):
    param = models.ForeignKey(FileParam, on_delete=models.CASCADE)
    allow_resultfiles = models.BooleanField(default=False)
    pset = models.ForeignKey(ParameterSet, on_delete=models.CASCADE)

    def __str__(self):
        return '{} -- {}'.format(self.pset.name, self.param.name)


class PsetMultiFileParam(models.Model):
    param = models.ForeignKey(FileParam, on_delete=models.CASCADE)
    allow_resultfiles = models.BooleanField(default=False)
    pset = models.ForeignKey(ParameterSet, on_delete=models.CASCADE)

    def __str__(self):
        return '{} -- {}'.format(self.pset.name, self.param.name)


class PsetParam(models.Model):
    param = models.ForeignKey(Param, on_delete=models.CASCADE)
    pset = models.ForeignKey(ParameterSet, on_delete=models.CASCADE)

    def __str__(self):
        return '{} -- {}'.format(self.pset.name, self.param.name)


class Analysis(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.TextField()
    log = models.JSONField(default=list)
    deleted = models.BooleanField(default=False)
    purged = models.BooleanField(default=False)
    storage_dir = models.TextField()


# Can this be generalized to deleted log for also files?
class AnalysisDeleted(models.Model):
    analysis = models.OneToOneField(Analysis, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)


class AnalysisError(models.Model):
    message = models.TextField()
    analysis = models.OneToOneField(Analysis, on_delete=models.CASCADE)


class NextflowSearch(models.Model):
    nfwfversionparamset = models.ForeignKey(NextflowWfVersionParamset, on_delete=models.CASCADE)
    workflow = models.ForeignKey(UserWorkflow, on_delete=models.CASCADE)
    analysis = models.OneToOneField(Analysis, on_delete=models.CASCADE)
    # token is for authentication of NF with-weblog
    token = models.TextField()
    job = models.OneToOneField(jmodels.Job, on_delete=models.CASCADE)


class AnalysisResultFile(models.Model):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    sfile = models.OneToOneField(filemodels.StoredFile, on_delete=models.CASCADE)


class Proteowizard(models.Model):
    version_description = models.TextField()
    container_version = models.TextField() # chambm/i-agree-blabla:3.0.1234
    date_added = models.DateTimeField(auto_now_add=True)
    is_docker = models.BooleanField(default=False)
    nf_version = models.ForeignKey(NextflowWfVersionParamset, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)


class MzmlFile(models.Model):
    sfile = models.OneToOneField(filemodels.StoredFile, on_delete=models.CASCADE)
    pwiz = models.ForeignKey(Proteowizard, on_delete=models.CASCADE)
    refined = models.BooleanField(default=False)


class EnsemblFasta(models.Model):
    libfile = models.OneToOneField(LibraryFile, on_delete=models.CASCADE)
    version = models.IntegerField()
    organism = models.TextField()


class UniProtFasta(models.Model):
    class UniprotClass(models.IntegerChoices):
        SWISS = 0, 'Swiss_canonical'
        SWISS_ISOFORMS = 1, 'Swiss_canonical_isoforms'
        REFERENCE = 2, 'Reference_proteome'
        REFERENCE_ISOFORMS = 3, 'Reference_proteome_isoforms'
    url_addons = {'SWISS': ' AND (reviewed:true)',
            'SWISS_ISOFORMS': ' AND (reviewed:true)&includeIsoform=true',
            'REFERENCE': '',
            'REFERENCE_ISOFORMS': '&includeIsoform=true',
            }

    libfile = models.OneToOneField(LibraryFile, on_delete=models.CASCADE)
    version = models.TextField()
    organism = models.TextField()
    #organismcode = models.IntegerField()
    dbtype = models.IntegerField(choices=UniprotClass.choices)


class AnalysisParam(models.Model):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    param = models.ForeignKey(Param, on_delete=models.CASCADE)
    value = models.JSONField() # can be option_id value, list of those, bool, or text/number input

    class Meta:
        constraints = [models.UniqueConstraint(fields=['analysis', 'param'], name='uni_anaparam')]


class AnalysisSampletable(models.Model):
    analysis = models.OneToOneField(Analysis, on_delete=models.CASCADE)
    samples = models.JSONField()
    # FIXME could we instead do: four columns channel - set - sample - group ?
    # Doesnt give a big improvement, if wf sampletable format will change, this DB table will change
    # But then we can keep representation correct instead of leaving the JSON intact
    # I don't see the JSON benefit except somewhat easier because it's passed around as JSON a lot
    # Added benefit: clearer DB representation, stricter


class AnalysisSetname(models.Model):
    '''All set or sample names in an analysis that are per dataset,
    which means prefractionated proteomics data'''
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    setname = models.TextField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['analysis', 'setname'], name='uni_anasets')]


class AnalysisDatasetSetname(models.Model):
    '''Dataset mapping to setnames (multiple dataset can have the same setname)'''
    # Note that datasets can be deleted, or have their file contents changed
    # That means this is not to be trusted for future bookkeeping of what was in the analysis
    # For that, you should combine it with using the below AnalysisDSInputFile model
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    dataset = models.ForeignKey(dsmodels.Dataset, on_delete=models.CASCADE)
    setname = models.ForeignKey(AnalysisSetname, on_delete=models.CASCADE, null=True)
    regex = models.TextField() # optional

    class Meta:
        constraints = [models.UniqueConstraint(fields=['analysis', 'dataset'], name='uni_anadsets')]

# FIXME how should we do with pgt DBGEN input? Are those sets, or are they something else?
# they def have sample names, and can be multiple per sample (BAMs merged, VCFs indel/snv etc)

class AnalysisDSInputFile(models.Model):
    '''Input files for set-based analysis (isobaric and prefraction-datasets)'''
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    sfile = models.ForeignKey(filemodels.StoredFile, on_delete=models.CASCADE)
    analysisdset = models.ForeignKey(AnalysisDatasetSetname, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['analysis', 'sfile'], name='uni_anainfile')]


class AnalysisFileSample(models.Model):
    '''If one sample per file is used in labelfree analyses, the samples are stored
    here'''
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    sample = models.TextField()
    sfile = models.ForeignKey(filemodels.StoredFile, on_delete=models.CASCADE)

    # FIXME this should maybe FK to infile above here?
    class Meta:
        constraints = [models.UniqueConstraint(fields=['analysis', 'sfile'], name='uni_anassamplefile')]


class DatasetAnalysis(models.Model):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    dataset = models.ForeignKey(dsmodels.Dataset, on_delete=models.CASCADE)
    # cannot put setname here because of searches without dset/setname
    # model used in reporting, and also for finding datasets for base analysis etc


class AnalysisIsoquant(models.Model):
    # FIXME can we not split the JSON field into denoms -JSON, 2x boolean, default=False?
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    setname = models.ForeignKey(AnalysisSetname, on_delete=models.CASCADE)
    #{denoms: [ch_id, ch_id], sweep: false, report_intensity: false}
    value = models.JSONField() 

    class Meta:
        constraints = [models.UniqueConstraint(fields=['analysis', 'setname'], name='uni_anaiso')]

class AnalysisFileParam(models.Model):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    param = models.ForeignKey(FileParam, on_delete=models.CASCADE)
    sfile = models.ForeignKey(filemodels.StoredFile, on_delete=models.CASCADE)

    # Multifiles makes this useless? Can still put in more files than needed with a race, just not
    # duplicates FIXME
    class Meta:
        constraints = [models.UniqueConstraint(fields=['analysis', 'param', 'sfile'], name='uni_anafileparam')]


class AnalysisBaseanalysis(models.Model):
    analysis = models.OneToOneField(Analysis, on_delete=models.CASCADE, related_name='analysis')
    base_analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE, related_name='base_analysis')
    is_complement = models.BooleanField(default=False)
    rerun_from_psms = models.BooleanField(default=False)
    # we can theoretically get shadow_ from analysisisoquant, but what if we have a recursive base analysis
    # then we have to get the base analysis' base analysis isoquant. Instead accumulate here in JSON
    shadow_isoquants = models.JSONField() # {setname: {ch: [sample, chid]} ...}
    shadow_dssetnames = models.JSONField() # {dsid: {setname: abc, regex: .*fr01} ...}
