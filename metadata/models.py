from django.db import models
from django.contrib.auth.models import User
from rawstatus.models import RawFile


class Dataset(models.Model):
    user = models.ForeignKey(User)
    date = models.DateTimeField('date created')
    project = models.CharField(max_length=100)
    experiment = models.CharField(max_length=100)


class DatasetRawFile(models.Model):
    dataset = models.ForeignKey(Dataset)
    rawfile = models.ForeignKey(RawFile)


class DatasetPI(models.Model):
    dataset = models.ForeignKey(Dataset)
    contact_email = models.CharField(max_length=100)


class DatasetContact(models.Model):
    """Exteral contacts if not PI can be entered in here"""
    dataset = models.ForeignKey(Dataset)
    contact_email = models.CharField(max_length=100)


class DraftDataset(models.Model):
    user = models.ForeignKey(User)
    mongoid = models.CharField(max_length=100)
    date = models.DateField('date created')
