from django.db import models


class Job(models.Model):
    funcname = models.CharField(max_length=100)
    args = models.CharField(max_length=10000)
    kwargs = models.CharField(max_length=10000)
    jobtype = models.CharField(max_length=50)
    timestamp = models.DateTimeField()
    state = models.CharField(max_length=10)  # pending, processing, error, done


class JobError(models.Model):
    job = models.OneToOneField(Job)
    message = models.TextField()


class Task(models.Model):
    asyncid = models.CharField(max_length=50)
    job = models.ForeignKey(Job)
    state = models.CharField(max_length=20)


class TaskChain(models.Model):
    lasttask = models.CharField(max_length=50)
    task = models.ForeignKey(Task)


class TaskError(models.Model):
    task = models.OneToOneField(Task)
    message = models.TextField()
