from django.db import models
from django.contrib.auth.models import User

from rawstatus import models as filemodels
from datasets import models as dsmodels
from jobs import models as jmodels


class NextflowWorkflow(models.Model):
    description = models.CharField(max_length=200, help_text='Description of workflow')
    repo = models.CharField(max_length=100)
    
    def __str__(self):
        return self.description


class NextflowWfVersion(models.Model):
    update = models.CharField(max_length=200, help_text='Description of workflow update')
    commit = models.CharField(max_length=50)
    filename = models.CharField(max_length=50)
    nfworkflow = models.ForeignKey(NextflowWorkflow)
    date = models.DateTimeField(auto_now=True)
    

class Analysis(models.Model):
    date = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User)
    name = models.CharField(max_length=100)


class AnalysisError(models.Model):
    message = models.TextField()
    analysis = models.OneToOneField(Analysis)


class NextflowSearch(models.Model):
    nfworkflow = models.ForeignKey(NextflowWfVersion)
    analysis = models.OneToOneField(Analysis)
    job = models.OneToOneField(jmodels.Job)


class DatasetSearch(models.Model):
    analysis = models.ForeignKey(Analysis)
    dataset = models.ForeignKey(dsmodels.Dataset)


class SearchResultFile(models.Model):
    analysis = models.ForeignKey(Analysis)


class LibraryFile(models.Model):
    description = models.CharField(max_length=100)
    sfile = models.ForeignKey(filemodels.StoredFile)
