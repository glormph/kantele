from django.db import models


class Job(models.Model):
    funcname = models.CharField(max_length=100)
    args = models.CharField(max_length=100000)
    kwargs = models.CharField(max_length=100000)
    timestamp = models.DateTimeField()
    state = models.CharField(max_length=10)  # pending, processing, error, done


class JobError(models.Model):
    job = models.OneToOneField(Job, on_delete=models.CASCADE)
    message = models.TextField()


class Task(models.Model):
    asyncid = models.CharField(max_length=50)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    state = models.CharField(max_length=20)
    args = models.TextField()


class TaskChain(models.Model):
    lasttask = models.CharField(max_length=50)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)


class TaskError(models.Model):
    task = models.OneToOneField(Task, on_delete=models.CASCADE)
    message = models.TextField()
