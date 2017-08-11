from django.db import models
from django.contrib.auth.models import User
from rawstatus.models import RawFile


class PrincipalInvestigator(models.Model):
    name = models.TextField(max_length=100)

    def __str__(self):
        return self.name


class Project(models.Model):
    name = models.CharField(max_length=100)
    pi = models.ForeignKey(PrincipalInvestigator)
    corefac = models.BooleanField()


class Datatype(models.Model):
    name = models.TextField(max_length=100)

    def __str__(self):
        return self.name


class Dataset(models.Model):
    user = models.ForeignKey(User)
    date = models.DateTimeField('date created')
    experiment = models.CharField(max_length=100)
    project = models.ForeignKey(Project)
    datatype = models.ForeignKey(Datatype)


class HiriefRange(models.Model):
    start = models.DecimalField(max_digits=5, decimal_places=2)
    end = models.DecimalField(max_digits=5, decimal_places=2)

    def __str__(self):
        return '{} - {}'.format(self.start, self.end)


class HiriefDataset(models.Model):
    dataset = models.ForeignKey(Dataset)
    hirief = models.ForeignKey(HiriefRange)


class CorefacDatasetContact(models.Model):
    dataset = models.ForeignKey(Dataset)
    email = models.CharField(max_length=100)


class DatasetRawFile(models.Model):
    dataset = models.ForeignKey(Dataset)
    rawfile = models.ForeignKey(RawFile)
