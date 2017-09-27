from django.db import models


class Job(models.Model):
    function = models.CharField(max_length=100)
    type = models.CharField(max_length=50)
    timestamp = models.DateTimeField()


class Task(models.Model):
    asyncid = models.CharField(max_length=50)
    job = models.ForeignKey(Job)
