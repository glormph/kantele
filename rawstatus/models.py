from django.db import models


class Producer(models.Model):
    name = models.CharField(max_length=100)
    client_id = models.CharField()  # for registration, UUID or perhaps auth
    heartbeat = models.DateTimeField('last seen')


class RawFile(models.Model):
    name = models.CharField()
    producer = models.ForeignKey(Producer)
    source_md5 = models.CharField()
    size = models.IntegerField('size in bytes')
    date = models.DateTimeField('date created')


class TransferredFile(models.Model):
    fileid = models.ForeignKey(RawFile)
    md5 = models.CharField()
