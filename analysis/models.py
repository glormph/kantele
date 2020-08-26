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
    sfile = models.OneToOneField(filemodels.StoredFile)

    def __str__(self):
        return self.description


class FileParam(models.Model):
    name = models.CharField(max_length=50)
    nfparam = models.CharField(max_length=50)
    filetype = models.ForeignKey(filemodels.StoredFileType)

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
    param = models.ForeignKey(Param)
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
    shortname = models.ForeignKey(WorkflowType)
    nfworkflow = models.ForeignKey(NextflowWorkflow)
    public = models.BooleanField()

    def __str__(self):
        return self.name


class NextflowWfVersion(models.Model):
    update = models.CharField(max_length=200, help_text='Description of workflow update')
    commit = models.CharField(max_length=50)
    filename = models.CharField(max_length=50)
    nfworkflow = models.ForeignKey(NextflowWorkflow)
    paramset = models.ForeignKey(ParameterSet)
    date = models.DateTimeField(auto_now=True)
    kanteleanalysis_version = models.IntegerField() # TODO remove this when noone uses v1 anymore
    nfversion = models.TextField()
    
    def __str__(self):
        return '{} - {}'.format(self.nfworkflow.description, self.update)


class PsetFileParam(models.Model):
    param = models.ForeignKey(FileParam)
    allow_resultfiles = models.BooleanField(default=False)
    pset = models.ForeignKey(ParameterSet)

    def __str__(self):
        return '{} -- {}'.format(self.pset.name, self.param.name)


class PsetMultiFileParam(models.Model):
    param = models.ForeignKey(FileParam)
    allow_resultfiles = models.BooleanField(default=False)
    pset = models.ForeignKey(ParameterSet)

    def __str__(self):
        return '{} -- {}'.format(self.pset.name, self.param.name)

# TODO get rid of predefined files, put them in some workflow config file instead
class PsetPredefFileParam(models.Model):
    param = models.ForeignKey(FileParam)
    libfile = models.ForeignKey(LibraryFile)
    pset = models.ForeignKey(ParameterSet)

    def __str__(self):
        return '{} -- {} -- {}'.format(self.pset.name, self.param.name, self.libfile.description)


class PsetParam(models.Model):
    param = models.ForeignKey(Param)
    pset = models.ForeignKey(ParameterSet)

    def __str__(self):
        return '{} -- {}'.format(self.pset.name, self.param.name)


class Analysis(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User)
    name = models.CharField(max_length=500)
    log = models.TextField(default='')
    deleted = models.BooleanField(default=False)
    purged = models.BooleanField(default=False)


# Can this be generalized to deleted log for also files?
class AnalysisDeleted(models.Model):
    analysis = models.OneToOneField(Analysis)
    date = models.DateTimeField(auto_now_add=True)


class AnalysisError(models.Model):
    message = models.TextField()
    analysis = models.OneToOneField(Analysis)


class NextflowSearch(models.Model):
    nfworkflow = models.ForeignKey(NextflowWfVersion)
    workflow = models.ForeignKey(Workflow)
    analysis = models.OneToOneField(Analysis)
    job = models.OneToOneField(jmodels.Job)


class DatasetSearch(models.Model):
    analysis = models.ForeignKey(Analysis)
    dataset = models.ForeignKey(dsmodels.Dataset)


class AnalysisResultFile(models.Model):
    analysis = models.ForeignKey(Analysis)
    sfile = models.OneToOneField(filemodels.StoredFile)


class Proteowizard(models.Model):
    version_description = models.TextField()
    container_version = models.TextField() # chambm/i-agree-blabla:3.0.1234
    date_added = models.DateTimeField(auto_now_add=True)
    is_docker = models.BooleanField(default=False)
    nf_version = models.ForeignKey(NextflowWfVersion)


class MzmlFile(models.Model):
    sfile = models.OneToOneField(filemodels.StoredFile)
    pwiz = models.ForeignKey(Proteowizard)
    refined = models.BooleanField(default=False)


class EnsemblFasta(models.Model):
    libfile = models.OneToOneField(LibraryFile)
    version = models.IntegerField(unique=True)
    organism = models.TextField()


class UniProtFasta(models.Model):
    libfile = models.OneToOneField(LibraryFile)
    version = models.TextField(unique=True)
    organism = models.TextField()
    #organismcode = models.IntegerField()
    isoforms = models.BooleanField()
