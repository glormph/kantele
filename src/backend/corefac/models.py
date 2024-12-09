from django.db import models

from datasets import models as dm


class PrepOptionProtocol(models.Model):
    doi = models.TextField()
    version = models.TextField()
    paramopt = models.OneToOneField(dm.SampleprepParameterOption, on_delete=models.CASCADE)


class SamplePipeline(models.Model):
    name = models.TextField()


class PipelineStep(models.Model):
    pipeline = models.ForeignKey(SamplePipeline, on_delete=models.CASCADE)
    previous = models.OneToOneField('self', on_delete=models.CASCADE)#, related_name='prevstep_of')
    step = models.ForeignKey(dm.SampleprepParameterOption, on_delete=models.CASCADE)


class DatasetPipeline(models.Model):
    '''A prep pipeline can be reused in multiple datasets if needed - result of a sample
    prep can theoretically be used in e.g. DIA / DDA runs, etc'''
    pipeline = models.ForeignKey(SamplePipeline, on_delete=models.CASCADE)
    dataset = models.ForeignKey(dm.Dataset, on_delete=models.CASCADE)
    started = models.BooleanField(default=False)
    start = models.DateTimeField(auto_now=True)
    stop = models.DateTimeField(auto_now=True)


class SamplePrepFinished(models.Model):
    '''Technically we could track result-of-step-samples (and locations) but that would be too much
    bookkeeping in the lab'''
    # To start we ll only put start/stop on the pipeline in the UI, and then make the prep steps
    # finish inside it. Im not sure if we need detailed prep step tracking
    sample = models.ForeignKey(dm.ProjectSample, on_delete=models.CASCADE)
    step = models.ForeignKey(PipelineStep, on_delete=models.CASCADE)
    finished = models.DateTimeField(auto_now=True)


#class ILabToken(models.Model):
#    token = models.TextField()
#    # expires for warning
#    expires = models.DateTimeField()
#
#
#class ProjectIlab(models.Model):
#    project = models.ForeignKey(dm.Project, on_delete=models.CASCADE)
#    ilab_id = models.TextField()
#
#
#class Location(models.Model):
#    # freezers and such
#    name = models.TextField()
#
#
#class SampleLocation(models.Model):
#    # Create new on each location change
#    location = models.ForeignKey(Location, on_delete=models.CASCADE)
#    sample = models.ForeignKey(dm.ProjectSample, on_delete=models.CASCADE)
#    timestamp = models.DateTimeField(auto_now_add=True)
#
#


    
