from django.db import models
from django.contrib.auth.models import User
from rawstatus.models import RawFile
from jobs.models import Job


class PrincipalInvestigator(models.Model):
    name = models.TextField(max_length=100)

    def __str__(self):
        return self.name


class Project(models.Model):
    name = models.CharField(max_length=100)
    pi = models.ForeignKey(PrincipalInvestigator, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)
    registered = models.DateTimeField(auto_now_add=True)


class ProjectTypeName(models.Model):
    name = models.CharField(max_length=50)


class ProjType(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE)
    ptype = models.ForeignKey(ProjectTypeName, on_delete=models.CASCADE)


class UserPtype(models.Model):
    ptype = models.ForeignKey(ProjectTypeName, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class Experiment(models.Model):
    name = models.CharField(max_length=200)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)


class RunName(models.Model):
    name = models.TextField(max_length=100)
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)


class Species(models.Model):
    linnean = models.TextField(unique=True)
    popname = models.TextField()


class Datatype(models.Model):
    name = models.TextField(max_length=100)
    public = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class DatasetComponent(models.Model):
    name = models.TextField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class DatatypeComponent(models.Model):
    datatype = models.ForeignKey(Datatype, on_delete=models.CASCADE)
    component = models.ForeignKey(DatasetComponent, on_delete=models.CASCADE)

    def __str__(self):
        return '{} has component {}'.format(self.datatype.name,
                                            self.component.name)


class Dataset(models.Model):
    date = models.DateTimeField('date created')
    runname = models.OneToOneField(RunName, on_delete=models.CASCADE)
    datatype = models.ForeignKey(Datatype, on_delete=models.CASCADE)
    storage_loc = models.TextField(max_length=200, unique=True)
    deleted = models.BooleanField(default=False) # for UI only, indicate deleted from active storage
    purged = models.BooleanField(default=False) # for UI only, indicate permanent deleted from cold storage too


class DatasetOwner(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class DatasetComponentState(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    dtcomp = models.ForeignKey(DatatypeComponent, on_delete=models.CASCADE)
    state = models.TextField(max_length=20)
    # state can be new, OK


class DatasetRawFile(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    rawfile = models.OneToOneField(RawFile, on_delete=models.CASCADE)


class DatasetSpecies(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    species = models.ForeignKey(Species, on_delete=models.CASCADE)


class ParamType(models.Model):
    typename = models.CharField(max_length=100)

    def __str__(self):
        return self.typename


class ParamLabcategory(models.Model):
    labcategory = models.CharField(max_length=100)

    def __str__(self):
        return self.labcategory


class SelectParameter(models.Model):
    # adminable
    title = models.CharField(max_length=100)
    category = models.ForeignKey(ParamLabcategory, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class FieldParameter(models.Model):
    # adminable
    title = models.CharField(max_length=100)
    placeholder = models.CharField(max_length=100)
    paramtype = models.ForeignKey(ParamType, on_delete=models.CASCADE)
    category = models.ForeignKey(ParamLabcategory, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class SelectParameterOption(models.Model):
    param = models.ForeignKey(SelectParameter, on_delete=models.CASCADE)
    value = models.CharField(max_length=100)

    def __str__(self):
        return self.value


class SelectParameterValue(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    value = models.ForeignKey(SelectParameterOption, on_delete=models.CASCADE)


class FieldParameterValue(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    param = models.ForeignKey(FieldParameter, on_delete=models.CASCADE)
    value = models.CharField(max_length=100)


class CheckboxParameter(models.Model):
    # adminable
    title = models.CharField(max_length=100)
    category = models.ForeignKey(ParamLabcategory, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class CheckboxParameterOption(models.Model):
    param = models.ForeignKey(CheckboxParameter, on_delete=models.CASCADE)
    value = models.CharField(max_length=100)

    def __str__(self):
        return self.value


class CheckboxParameterValue(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    value = models.ForeignKey(CheckboxParameterOption, on_delete=models.CASCADE)


class Enzyme(models.Model):
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name


class EnzymeDataset(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    enzyme = models.ForeignKey(Enzyme, on_delete=models.CASCADE)


class QuantType(models.Model):
    name = models.CharField(max_length=20)
    shortname = models.CharField(max_length=15)

    def __str__(self):
        return self.name


class QuantChannel(models.Model):
    name = models.CharField(max_length=20)

    def __str__(self):
        return self.name


class QuantTypeChannel(models.Model):
    quanttype = models.ForeignKey(QuantType, on_delete=models.CASCADE)
    channel = models.ForeignKey(QuantChannel, on_delete=models.CASCADE)

    def __str__(self):
        return '{} - {}'.format(self.quanttype.name, self.channel.name)


class QuantDataset(models.Model):
    dataset = models.OneToOneField(Dataset, on_delete=models.CASCADE)
    quanttype = models.ForeignKey(QuantType, on_delete=models.CASCADE)


class ProjectSample(models.Model):
    sample = models.CharField(max_length=100)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    class Meta:
        unique_together = [['sample', 'project']]


class QuantSampleFile(models.Model):
    rawfile = models.OneToOneField(DatasetRawFile, on_delete=models.CASCADE)
    projsample = models.ForeignKey(ProjectSample, on_delete=models.CASCADE)


class QuantChannelSample(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    channel = models.ForeignKey(QuantTypeChannel, on_delete=models.CASCADE)
    projsample = models.ForeignKey(ProjectSample, on_delete=models.CASCADE)


class QuantFileChannelSample(models.Model):  # used for labelcheck
    channel = models.ForeignKey(QuantTypeChannel, on_delete=models.CASCADE)
    projsample = models.ForeignKey(ProjectSample, on_delete=models.CASCADE)
    dsrawfile = models.OneToOneField(DatasetRawFile, on_delete=models.CASCADE)
    

class HiriefRange(models.Model):
    # adminable
    start = models.DecimalField(max_digits=5, decimal_places=2)
    end = models.DecimalField(max_digits=5, decimal_places=2)

    def __str__(self):
        return '{} - {}'.format(self.start, self.end)

    def get_path(self):
        return '{}_{}'.format(self.start, self.end)


class ExternalDatasetContact(models.Model):
    dataset = models.OneToOneField(Dataset, on_delete=models.CASCADE)
    email = models.CharField(max_length=100)


class Operator(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def __str__(self):
        return '{} {}'.format(self.user.first_name, self.user.last_name)


class OperatorDataset(models.Model):
    dataset = models.OneToOneField(Dataset, on_delete=models.CASCADE)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)


class ReversePhaseDataset(models.Model):
    dataset = models.OneToOneField(Dataset, on_delete=models.CASCADE)
    length = models.CharField(max_length=20)


class Prefractionation(models.Model):
    name = models.CharField(max_length=20)

    def __str__(self):
        return self.name


class PrefractionationDataset(models.Model):
    dataset = models.OneToOneField(Dataset, on_delete=models.CASCADE)
    prefractionation = models.ForeignKey(Prefractionation, on_delete=models.CASCADE)


class HiriefDataset(models.Model):
    pfdataset = models.OneToOneField(PrefractionationDataset, on_delete=models.CASCADE)
    hirief = models.ForeignKey(HiriefRange, on_delete=models.CASCADE)


class PrefractionationLength(models.Model):
    pfdataset = models.OneToOneField(PrefractionationDataset, on_delete=models.CASCADE)
    length = models.CharField(max_length=20)


class PrefractionationFractionAmount(models.Model):
    pfdataset = models.OneToOneField(PrefractionationDataset, on_delete=models.CASCADE)
    fractions = models.IntegerField()


class DatasetJob(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
