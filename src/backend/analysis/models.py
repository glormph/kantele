from django.db import models
from django.contrib.auth.models import User

from rawstatus import models as filemodels
from datasets import models as dsmodels
from jobs import models as jmodels


class WorkflowType(models.Model):
    name = models.TextField()

    def __str__(self):
        return self.name


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


class WFInputComponent(models.Model):
    name = models.TextField()
    value = models.JSONField() 
    # JSON in value if any, eg mzmldef: {'lc': [path,ch,sample], 'lcp': [path,set,ch,sam], hirief: [path,inst,set,pl,fr]}
    # FIXME future also setnames, sampletables, fractions, etc which is not a param
    # to be included in parameterset
    def __str__(self):
        return self.name


class Param(models.Model):
    name = models.TextField()
    nfparam = models.TextField()
    ptype = models.TextField()  # multi (options), number, flag or ...
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


class NextflowWorkflow(models.Model):
    description = models.TextField(help_text='Description of workflow')
    repo = models.TextField()
    
    def __str__(self):
        return self.description


class Workflow(models.Model):
    name = models.TextField()
    shortname = models.ForeignKey(WorkflowType, on_delete=models.CASCADE)
    nfworkflow = models.ForeignKey(NextflowWorkflow, on_delete=models.CASCADE)
    public = models.BooleanField()

    def __str__(self):
        return self.name


class NextflowWfVersion(models.Model):
    update = models.TextField(help_text='Description of workflow update')
    commit = models.CharField(max_length=50)
    filename = models.TextField()
    profiles = models.JSONField(default=list)
    nfworkflow = models.ForeignKey(NextflowWorkflow, on_delete=models.CASCADE)
    paramset = models.ForeignKey(ParameterSet, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now=True)
    kanteleanalysis_version = models.IntegerField() # TODO remove this when noone uses v1 anymore
    nfversion = models.TextField()

    def __str__(self):
        return '{} - {}'.format(self.nfworkflow.description, self.update)


class WfOutput(models.Model):
    nfwfversion = models.OneToOneField(NextflowWfVersion, on_delete=models.CASCADE)
    psmfile = models.TextField()
    pepfile = models.TextField()
    lookup = models.TextField()
    peppeptide = models.TextField()
    psmcountfield = models.TextField()
    pepfdrfield = models.TextField()
    psmfdrfield = models.TextField()
    psmfnfield = models.TextField()
    scanfield = models.TextField()
    psmscorefield = models.TextField()
    # need score type?
    psmsetname = models.TextField()
    psmpeptide = models.TextField()


class PsetComponent(models.Model):
    pset = models.ForeignKey(ParameterSet, on_delete=models.CASCADE)
    component = models.ForeignKey(WFInputComponent, on_delete=models.CASCADE)

    def __str__(self):
        return '{} - {}'.format(self.pset.name, self.component.name)


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

# TODO get rid of predefined files, put them in some workflow config file instead
class PsetPredefFileParam(models.Model):
    param = models.ForeignKey(FileParam, on_delete=models.CASCADE)
    libfile = models.ForeignKey(LibraryFile, on_delete=models.CASCADE)
    pset = models.ForeignKey(ParameterSet, on_delete=models.CASCADE)

    def __str__(self):
        return '{} -- {} -- {}'.format(self.pset.name, self.param.name, self.libfile.description)


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
    nfworkflow = models.ForeignKey(NextflowWfVersion, on_delete=models.CASCADE)
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE)
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
    nf_version = models.ForeignKey(NextflowWfVersion, on_delete=models.CASCADE)
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
    # could we instead do: four columns channel - set - sample - group ?
    # Doesnt give a big improvement, if wf sampletable format will change, this DB table will change
    # But then we can keep representation correct instead of leaving the JSON intact
    # I don't see the JSON benefit except somewhat easier because it's passed around as JSON a lot


class AnalysisMzmldef(models.Model):
    analysis = models.OneToOneField(Analysis, on_delete=models.CASCADE)
    mzmldef = models.TextField()


class AnalysisSetname(models.Model):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    setname = models.TextField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['analysis', 'setname'], name='uni_anasets')]


class AnalysisDatasetSetname(models.Model):
    # Note that datasets can be deleted, or have their file contents changed
    # That means this is not to be trusted for future bookkeeping of what was in the analysis
    # For that, you should combine it with using the below AnalysisDSInputFile model
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    dataset = models.ForeignKey(dsmodels.Dataset, on_delete=models.CASCADE)
    setname = models.ForeignKey(AnalysisSetname, on_delete=models.CASCADE, null=True)
    regex = models.TextField() # optional

    class Meta:
        constraints = [models.UniqueConstraint(fields=['analysis', 'dataset'], name='uni_anadsets')]


class AnalysisDSInputFile(models.Model):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    sfile = models.ForeignKey(filemodels.StoredFile, on_delete=models.CASCADE)
    analysisdset = models.ForeignKey(AnalysisDatasetSetname, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['analysis', 'sfile'], name='uni_anainfile')]


class AnalysisFileSample(models.Model):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    sample = models.TextField()
    sfile = models.ForeignKey(filemodels.StoredFile, on_delete=models.CASCADE)

    # FIXME this should maybe FK to infile above here?
    class Meta:
        constraints = [models.UniqueConstraint(fields=['analysis', 'sfile'], name='uni_anassamplefile')]


class DatasetSearch(models.Model):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    dataset = models.ForeignKey(dsmodels.Dataset, on_delete=models.CASCADE)
    # cannot put setname here because of searches without dset/setname
    # purely a reporting model this is


class AnalysisIsoquant(models.Model):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    setname = models.ForeignKey(AnalysisSetname, on_delete=models.CASCADE)
    #{denoms: [ch_id, ch_id], sweep: false, intensity: false}
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
