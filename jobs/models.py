from django.db import models


class Job(models.Model):
    funcname = models.CharField(max_length=100)
    args = models.CharField(max_length=300)
    kwargs = models.CharField(max_length=300)
    jobtype = models.CharField(max_length=50)
    timestamp = models.DateTimeField()
    state = models.CharField(max_length=10)  # pending, processing, error, done


class JobError(models.Model):
    job = models.OneToOneField(Job)
    message = models.CharField(max_length=200)
    autorequeue = models.BooleanField()


class Task(models.Model):
    asyncid = models.CharField(max_length=50)
    job = models.ForeignKey(Job)
    state = models.CharField(max_length=20)
