from django.db import models


class AnalysisResult(models.Model):
    date = models.DateTimeField()


class GalaxyResult(models.Model):
    analysis = models.ForeignKey(AnalysisResult)
