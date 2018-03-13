from django.db import models

from jobs.models import Job


class Producer(models.Model):
    name = models.CharField(max_length=100)
    client_id = models.CharField(max_length=100)
    heartbeat = models.DateTimeField('last seen', auto_now=True)

    def __str__(self):
        return self.name


class ServerShare(models.Model):
    name = models.CharField(max_length=50, unique=True)  # storage, tmp,
    uri = models.CharField(max_length=100)  # uri storage.mydomain.com
    share = models.CharField(max_length=50)  # /home/disk1


class RawFile(models.Model):
    """Data (raw) files as reported by instrument"""
    name = models.CharField(max_length=100)
    producer = models.ForeignKey(Producer)
    source_md5 = models.CharField(max_length=32, unique=True)
    size = models.BigIntegerField('size in bytes')
    date = models.DateTimeField('date/time created')
    claimed = models.BooleanField()
    deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class StoredFile(models.Model):
    """Files transferred from instrument to storage"""
    rawfile = models.ForeignKey(RawFile)
    filename = models.CharField(max_length=200)
    # filetype raw==produced and has a rawfile entry, mzml etc is derivate
    filetype = models.CharField(max_length=20)
    servershare = models.ForeignKey(ServerShare)
    path = models.CharField(max_length=200)
    md5 = models.CharField(max_length=32)
    checked = models.BooleanField()

    def __str__(self):
        return self.rawfile.name


class SwestoreBackedupFile(models.Model):
    storedfile = models.OneToOneField(StoredFile)
    swestore_path = models.CharField(max_length=200)
    success = models.BooleanField()


class FileJob(models.Model):
    # FIXME move to job module
    storedfile = models.ForeignKey(StoredFile)
    job = models.ForeignKey(Job)
