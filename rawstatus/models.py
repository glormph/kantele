from django.db import models


class Producer(models.Model):
    name = models.CharField(max_length=100)
    client_id = models.CharField(max_length=100)
    heartbeat = models.DateTimeField('last seen', auto_now=True)

    def __str__(self):
        return self.name


class ServerShares(models.Model):
    name = models.CharField(max_length=50)  # storage, tmp,
    uri = models.CharField(max_length=100)  # uri storage.mydomain.com
    share = models.CharField(max_length=50)  # /home/disk1


class RawFile(models.Model):
    """Data (raw) files as reported by instrument"""
    name = models.CharField(max_length=100)
    producer = models.ForeignKey(Producer)
    source_md5 = models.CharField(max_length=32, unique=True)
    size = models.IntegerField('size in bytes')
    date = models.DateTimeField('date created')
    claimed = models.BooleanField()

    def __str__(self):
        return self.name


class StoredFile(models.Model):
    """Files transferred from instrument to storage"""
    rawfile = models.ForeignKey(RawFile)
    filetype = models.CharField(max_length=20)  # raw, fq, mzML, etc
    servershare = models.ForeignKey(ServerShares)
    path = models.CharField(max_length=200)
    md5 = models.CharField(max_length=32, blank=True)

    def __str__(self):
        return self.rawfile.name
