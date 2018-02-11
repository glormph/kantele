from django.db import models
from django.contrib.auth.models import User

from rawstatus import models as filemodels


class GalaxyWorkflow(models.Model):
    commit = models.CharField(max_length=50)
    wfjson = models.TextField()


class NextflowWorkflow(models.Model):
    repo = models.TextField()
    commit = models.CharField(max_length=50)
    filename = models.CharField(max_length=50)


class GalaxySearch(models.Model):
    searchtype = models.CharField(max_length=10)
    workflow = models.ForeignKey(GalaxyWorkflow)


class GalaxyAccount(models.Model):
    user = models.ForeignKey(User)
    apikey = models.CharField(max_length=32)


class AnalysisParams(models.Model):
    """paramjson = {'target db': GalaxyLibDataset.id, 'decoy db': etc"""
    creationdate = models.DateTimeField(auto_now=True)
    paramjson = models.TextField()


class Analysis(models.Model):
    date = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User)
    name = models.CharField(max_length=100)
    search = models.ForeignKey(GalaxySearch)
    account = models.ForeignKey(GalaxyAccount)
    params = models.ForeignKey(AnalysisParams)


class SearchMzmlFiles(models.Model):
    analysis = models.ForeignKey(Analysis)
    mzml = models.ForeignKey(filemodels.StoredFile)


class GalaxyResult(models.Model):
    analysis = models.ForeignKey(Analysis)


class LibraryFiles(models.Model):
    name = models.CharField(max_length=100)
    filetype = models.CharField(max_length=20)
    servershare = models.ForeignKey(ServerShare)
    path = models.CharField(max_length=200)
