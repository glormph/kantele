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
    ptype = models.CharField(max_length=10)  # file, flag or value
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


class DatasetSearch(models.Model):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    dataset = models.ForeignKey(dsmodels.Dataset, on_delete=models.CASCADE)
