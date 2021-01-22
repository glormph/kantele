from django.db import models
from django.contrib.auth.models import User

from rawstatus import models as filemodels
from datasets import models as dsmodels
from jobs import models as jmodels


class WorkflowType(models.Model):
    name = models.CharField(max_length=20)

    def __str__(self):
        return self.name


class LibraryFile(models.Model):
    description = models.CharField(max_length=100)
    sfile = models.OneToOneField(filemodels.StoredFile, on_delete=models.CASCADE)

    def __str__(self):
        return self.description


class FileParam(models.Model):
    name = models.CharField(max_length=50)
    nfparam = models.CharField(max_length=50)
    filetype = models.ForeignKey(filemodels.StoredFileType, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class WFInputComponent(models.Model):
    name = models.TextField()
    value = models.TextField() 
    # JSON in value if any, eg mzmldef: {'lc': [path,ch,sample], 'lcp': [path,set,ch,sam], hirief: [path,inst,set,pl,fr]}
    # FIXME future also setnames, sampletables, fractions, etc which is not a param
    # to be included in parameterset
    def __str__(self):
        return self.name


class Param(models.Model):
    name = models.CharField(max_length=50)
    nfparam = models.CharField(max_length=50)
    ptype = models.CharField(max_length=10)  # multi (options), number, flag or ...
    visible = models.BooleanField(default=True)

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
    description = models.CharField(max_length=200, help_text='Description of workflow')
    repo = models.CharField(max_length=100)
    
    def __str__(self):
        return self.description


class Workflow(models.Model):
    name = models.CharField(max_length=50)
    shortname = models.ForeignKey(WorkflowType, on_delete=models.CASCADE)
    nfworkflow = models.ForeignKey(NextflowWorkflow, on_delete=models.CASCADE)
    public = models.BooleanField()

    def __str__(self):
        return self.name


class NextflowWfVersion(models.Model):
    update = models.CharField(max_length=200, help_text='Description of workflow update')
    commit = models.CharField(max_length=50)
    filename = models.CharField(max_length=50)
    nfworkflow = models.ForeignKey(NextflowWorkflow, on_delete=models.CASCADE)
    paramset = models.ForeignKey(ParameterSet, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now=True)
    kanteleanalysis_version = models.IntegerField() # TODO remove this when noone uses v1 anymore
    nfversion = models.TextField()
    
    def __str__(self):
        return '{} - {}'.format(self.nfworkflow.description, self.update)


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
    name = models.CharField(max_length=500)
    log = models.TextField(default='')
    deleted = models.BooleanField(default=False)
    purged = models.BooleanField(default=False)


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


class MzmlFile(models.Model):
    sfile = models.OneToOneField(filemodels.StoredFile, on_delete=models.CASCADE)
    pwiz = models.ForeignKey(Proteowizard, on_delete=models.CASCADE)
    refined = models.BooleanField(default=False)


class EnsemblFasta(models.Model):
    libfile = models.OneToOneField(LibraryFile, on_delete=models.CASCADE)
    version = models.IntegerField()
    organism = models.TextField()


class UniProtFasta(models.Model):
    libfile = models.OneToOneField(LibraryFile, on_delete=models.CASCADE)
    version = models.TextField()
    organism = models.TextField()
    #organismcode = models.IntegerField()
    isoforms = models.BooleanField()


class AnalysisParam(models.Model):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    param = models.ForeignKey(Param, on_delete=models.CASCADE)
    value = models.JSONField() # can be option_id value, list of those, bool, or text/number input

    class Meta:
        constraints = [models.UniqueConstraint(fields=['analysis', 'param'], name='uni_anaparam')]


class AnalysisSampletable(models.Model):
    analysis = models.OneToOneField(Analysis, on_delete=models.CASCADE)
    samples = models.JSONField()


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
    # For that, you should combine it with using the below AnalysisDSInputfile model
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
    is_complement = models.BooleanField()
    # we can theoretically get shadow_ from analysisisoquant, but what if we have a recursive base analysis
    # then we have to get the base analysis' base analysis isoquant. Instead accumulate here in JSON
    shadow_isoquants = models.JSONField() # {setname: {ch: [sample, chid]} ...}
    shadow_dssetnames = models.JSONField() # {dsid: {setname: abc, regex: .*fr01} ...}
