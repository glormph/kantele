from django.db import models


class Job(models.Model):
    funcname = models.TextField()
    args = models.JSONField()
    kwargs = models.JSONField()
    timestamp = models.DateTimeField()
    state = models.TextField()  # pending, processing, error, done


class JobError(models.Model):
    job = models.OneToOneField(Job, on_delete=models.CASCADE)
    message = models.TextField()


class Task(models.Model):
    asyncid = models.CharField(max_length=50)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    state = models.TextField()
    args = models.JSONField()


class TaskChain(models.Model):
    lasttask = models.TextField()
    task = models.ForeignKey(Task, on_delete=models.CASCADE)


class TaskError(models.Model):
    task = models.OneToOneField(Task, on_delete=models.CASCADE)
    message = models.TextField()
