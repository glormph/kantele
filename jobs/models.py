from django.db import models


class Job(models.Model):
    function = models.CharField(max_length=100)
    jobtype = models.CharField(max_length=50)
    timestamp = models.DateTimeField()
    # FIXME since we have joberror table maybe state is not important
    # unless we can also have queued
    state = models.CharField(max_length=10)  # processing or error


class JobError(models.Model):
    job = models.OneToOneField(Job)
    message = models.CharField(max_length=200)
    autorequeue = models.BooleanField()


class Task(models.Model):
    asyncid = models.CharField(max_length=50)
    job = models.ForeignKey(Job)
