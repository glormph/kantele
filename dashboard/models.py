from django.db import models

from rawstatus import models as filemodels
from analysis import models as analysismodels


class QCData(models.Model):
    rawfile = models.ForeignKey(filemodels.RawFile)
    analysis = models.ForeignKey(analysismodels.Analysis)


class Plot(models.Model):
    shortname = models.CharField(max_length=10)
    title = models.CharField(max_length=50)


class LineplotData(models.Model):
    plot = models.ForeignKey(Plot)
    qcrun = models.ForeignKey(QCData)
    value = models.FloatField()
    category = models.CharField(max_length=20)


class BoxplotData(models.Model):
    plot = models.ForeignKey(Plot)
    qcrun = models.ForeignKey(QCData)
    upper = models.FloatField()
    lower = models.FloatField()
    q1 = models.FloatField()
    q2 = models.FloatField()
    q3 = models.FloatField()
