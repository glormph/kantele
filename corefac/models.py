from django.db import models
from django.contrib.auth.models import User


class CorefacUser(models.Model):
    user = models.ForeignKey(User)
