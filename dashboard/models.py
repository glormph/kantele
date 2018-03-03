from django.db import models

from rawstatus import models as filemodels
from analysis import models as analysismodels


class QCData(models.Model):
    rawfile = models.ForeignKey(filemodels.RawFile)
    analysis = models.ForeignKey(analysismodels.Analysis)


class LineplotData(models.Model):
    qcrun = models.ForeignKey(QCData)
    value = models.FloatField()
    shortname = models.CharField(max_length=20)


class BoxplotData(models.Model):
    shortname = models.CharField(max_length=15)
    qcrun = models.ForeignKey(QCData)
    upper = models.FloatField()
    lower = models.FloatField()
    q1 = models.FloatField()
    q2 = models.FloatField()
    q3 = models.FloatField()
