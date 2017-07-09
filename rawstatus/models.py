from django.db import models


class Producer(models.Model):
    name = models.CharField(max_length=100)
    client_id = models.CharField(max_length=100)
    heartbeat = models.DateTimeField('last seen', auto_now=True)

    def __str__(self):
        return self.name


class RawFile(models.Model):
    """Data (raw) files as reported by instrument"""
    name = models.CharField(max_length=100)
    producer = models.ForeignKey(Producer)
    source_md5 = models.CharField(max_length=32, unique=True)
    size = models.IntegerField('size in bytes')
    date = models.DateTimeField('date created')

    def __str__(self):
        return self.name


class TransferredFile(models.Model):
    """Files transferred from instrument to storage"""
    rawfile = models.ForeignKey(RawFile)
    fnpath = models.CharField(max_length=200)
    md5 = models.CharField(max_length=32, blank=True)

    def __str__(self):
        return self.rawfile.name
