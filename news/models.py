from django.db import models
from django.contrib.auth.models import User

class Entry(models.Model):
    author = models.ForeignKey(User)
    date = models.DateTimeField('date created')
    title = models.CharField(max_length=100)
    body = models.TextField()
