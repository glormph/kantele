from django.db import models
from django.contrib.auth.models import User

class Dataset(models.Model):
    user = models.ForeignKey(User)
    mongoid = models.CharField(max_length=100)
    date = models.DateField('date created')
    project = models.CharField(max_length=100)
    experiment = models.CharField(max_length=100)

    
class Template(models.Model):
    user = models.ForeignKey(User)
    mongoid = models.CharField(max_length=100)
    name = models.CharField(max_length=100) 
    date = models.DateField()


