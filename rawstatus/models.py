from django.db import models
from django.contrib.auth.models import User

from jobs.models import Job


class StoredFileType(models.Model):
    name = models.CharField(max_length=100, unique=True) 
    filetype = models.CharField(max_length=20) # fasta, tabular, mzml, raw, analysisoutput
    is_folder = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class MSInstrumentType(models.Model):
    name = models.TextField(unique=True) # timstof, qe, velos, tof, lcq, etc

    def __str__(self):
        return self.name


class Producer(models.Model):
    name = models.CharField(max_length=100)
    client_id = models.CharField(max_length=100)
    shortname = models.CharField(max_length=10)

    def __str__(self):
        return self.name


class MSInstrument(models.Model):
    producer = models.OneToOneField(Producer, on_delete=models.CASCADE)
    instrumenttype = models.ForeignKey(MSInstrumentType, on_delete=models.CASCADE)
    filetype = models.ForeignKey(StoredFileType, on_delete=models.CASCADE) # raw, .d
    active = models.BooleanField(default=True)

    def __str__(self):
        return 'MS - {}/{}'.format(self.producer.name, self.filetype.name)


class ServerShare(models.Model):
    name = models.CharField(max_length=50, unique=True)  # storage, tmp,
    uri = models.CharField(max_length=100)  # uri storage.mydomain.com
    share = models.CharField(max_length=50)  # /home/disk1


class RawFile(models.Model):
    """Data (raw) files as reported by instrument"""
    name = models.CharField(max_length=100)
    producer = models.ForeignKey(Producer, on_delete=models.CASCADE)
    source_md5 = models.CharField(max_length=32, unique=True)
    size = models.BigIntegerField('size in bytes')
    date = models.DateTimeField('date/time created')
    claimed = models.BooleanField()

    def __str__(self):
        return self.name


class StoredFile(models.Model):
    """Files transferred from instrument to storage"""
    rawfile = models.ForeignKey(RawFile, on_delete=models.CASCADE)
    filename = models.CharField(max_length=200)
    servershare = models.ForeignKey(ServerShare, on_delete=models.CASCADE)
    path = models.CharField(max_length=200)
    regdate = models.DateTimeField(auto_now_add=True)
    md5 = models.CharField(max_length=32)
    checked = models.BooleanField()
    # TODO put filetype on the RawFile instead of storedfile? Possible?
    filetype = models.ForeignKey(StoredFileType, on_delete=models.CASCADE)
    deleted = models.BooleanField(default=False) # marked for deletion by user, only UI
    purged = models.BooleanField(default=False) # deleted from active storage filesystem

    def __str__(self):
        return self.rawfile.name


class UserFileUpload(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    filetype = models.ForeignKey(StoredFileType, on_delete=models.CASCADE)
    token = models.CharField(max_length=36, unique=True) # UUID keys
    timestamp = models.DateTimeField(auto_now=True) # this can be updated
    expires = models.DateTimeField()
    finished = models.BooleanField(default=False)


class UserFile(models.Model):
    sfile = models.OneToOneField(StoredFile, on_delete=models.CASCADE)
    description = models.CharField(max_length=100)
    upload = models.OneToOneField(UserFileUpload, on_delete=models.CASCADE)


class PDCBackedupFile(models.Model):
    storedfile = models.OneToOneField(StoredFile, on_delete=models.CASCADE)
    pdcpath = models.TextField()
    success = models.BooleanField()
    deleted = models.BooleanField(default=False)


class SwestoreBackedupFile(models.Model):
    storedfile = models.OneToOneField(StoredFile, on_delete=models.CASCADE)
    swestore_path = models.CharField(max_length=200)
    success = models.BooleanField()
    deleted = models.BooleanField(default=False)


class FileJob(models.Model):
    # FIXME move to job module
    storedfile = models.ForeignKey(StoredFile, on_delete=models.CASCADE)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
