from django.db import models
from django.contrib.auth.models import User

from rawstatus import models as filemodels


class NextflowWorkflow(models.Model):
    repo = models.TextField()
    commit = models.CharField(max_length=50)
    filename = models.CharField(max_length=50)


class AnalysisParams(models.Model):
    """paramjson = {'target db': GalaxyLibDataset.id, 'decoy db': etc"""
    creationdate = models.DateTimeField(auto_now=True)
    paramjson = models.TextField()


class Analysis(models.Model):
    date = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User)
    name = models.CharField(max_length=100)
    params = models.ForeignKey(AnalysisParams)


class NextflowSearch(models.Model):
    nfworkflow = models.ForeignKey(NextflowWorkflow)
    params = models.TextField()
    analysis = models.OneToOneField(Analysis)


class SearchFiles(models.Model):
    analysis = models.ForeignKey(Analysis)
    sfile = models.ForeignKey(filemodels.StoredFile)


class SearchResultFile(models.Model):
    analysis = models.ForeignKey(Analysis)


class LibraryFiles(models.Model):
    description = models.CharField(max_length=100)
    sfile = models.ForeignKey(filemodels.StoredFile)
