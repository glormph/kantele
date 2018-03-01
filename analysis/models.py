from django.db import models
from django.contrib.auth.models import User

from rawstatus import models as filemodels


class NextflowWorkflow(models.Model):
    description = models.CharField(max_length=200, help_text='Description of workflow update')
    repo = models.CharField(max_length=100)
    commit = models.CharField(max_length=50)
    filename = models.CharField(max_length=50)
    
    def __str__(self):
        return self.description


class Analysis(models.Model):
    date = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User)
    name = models.CharField(max_length=100)


class NextflowSearch(models.Model):
    nfworkflow = models.ForeignKey(NextflowWorkflow)
    params = models.TextField()
    analysis = models.OneToOneField(Analysis)


class SearchFile(models.Model):
    search = models.ForeignKey(NextflowSearch)
    sfile = models.ForeignKey(filemodels.StoredFile)


class SearchResultFile(models.Model):
    analysis = models.ForeignKey(Analysis)


class LibraryFile(models.Model):
    description = models.CharField(max_length=100)
    sfile = models.ForeignKey(filemodels.StoredFile)
