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
    pi = models.ForeignKey(PrincipalInvestigator)
    corefac = models.BooleanField()


class Experiment(models.Model):
    name = models.CharField(max_length=200)
    project = models.ForeignKey(Project)


class RunName(models.Model):
    name = models.TextField(max_length=100)
    experiment = models.ForeignKey(Experiment)


class Species(models.Model):
    linnean = models.TextField(unique=True)
    popname = models.TextField()


class Datatype(models.Model):
    name = models.TextField(max_length=100)

    def __str__(self):
        return self.name


class DatasetComponent(models.Model):
    name = models.TextField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class DatatypeComponent(models.Model):
    datatype = models.ForeignKey(Datatype)
    component = models.ForeignKey(DatasetComponent)

    def __str__(self):
        return '{} has component {}'.format(self.datatype.name,
                                            self.component.name)


class Dataset(models.Model):
    user = models.ForeignKey(User)
    date = models.DateTimeField('date created')
    runname = models.OneToOneField(RunName)
    datatype = models.ForeignKey(Datatype)
    storage_loc = models.TextField(max_length=200, unique=True)


class DatasetComponentState(models.Model):
    dataset = models.ForeignKey(Dataset)
    dtcomp = models.ForeignKey(DatatypeComponent)
    state = models.TextField(max_length=20)
    # state can be new, OK


class DatasetRawFile(models.Model):
    dataset = models.ForeignKey(Dataset)
    rawfile = models.OneToOneField(RawFile)


class DatasetSpecies(models.Model):
    dataset = models.ForeignKey(Dataset)
    species = models.ForeignKey(Species)


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
    category = models.ForeignKey(ParamLabcategory)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class FieldParameter(models.Model):
    # adminable
    title = models.CharField(max_length=100)
    placeholder = models.CharField(max_length=100)
    paramtype = models.ForeignKey(ParamType)
    category = models.ForeignKey(ParamLabcategory)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class SelectParameterOption(models.Model):
    param = models.ForeignKey(SelectParameter)
    value = models.CharField(max_length=100)

    def __str__(self):
        return self.value


class SelectParameterValue(models.Model):
    dataset = models.ForeignKey(Dataset)
    value = models.ForeignKey(SelectParameterOption)


class FieldParameterValue(models.Model):
    dataset = models.ForeignKey(Dataset)
    param = models.ForeignKey(FieldParameter)
    value = models.CharField(max_length=100)


class CheckboxParameter(models.Model):
    # adminable
    title = models.CharField(max_length=100)
    category = models.ForeignKey(ParamLabcategory)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class CheckboxParameterOption(models.Model):
    param = models.ForeignKey(CheckboxParameter)
    value = models.CharField(max_length=100)

    def __str__(self):
        return self.value


class CheckboxParameterValue(models.Model):
    dataset = models.ForeignKey(Dataset)
    value = models.ForeignKey(CheckboxParameterOption)


class Enzyme(models.Model):
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name


class EnzymeDataset(models.Model):
    dataset = models.ForeignKey(Dataset)
    enzyme = models.ForeignKey(Enzyme)


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
    quanttype = models.ForeignKey(QuantType)
    channel = models.ForeignKey(QuantChannel)

    def __str__(self):
        return '{} - {}'.format(self.quanttype.name, self.channel.name)


class QuantDataset(models.Model):
    dataset = models.OneToOneField(Dataset)
    quanttype = models.ForeignKey(QuantType)


class QuantSampleFile(models.Model):
    rawfile = models.OneToOneField(DatasetRawFile)
    sample = models.CharField(max_length=100)


class QuantChannelSample(models.Model):
    dataset = models.ForeignKey(Dataset)
    channel = models.ForeignKey(QuantTypeChannel)
    sample = models.CharField(max_length=100)


class HiriefRange(models.Model):
    # adminable
    start = models.DecimalField(max_digits=5, decimal_places=2)
    end = models.DecimalField(max_digits=5, decimal_places=2)

    def __str__(self):
        return '{} - {}'.format(self.start, self.end)

    def get_path(self):
        return '{}_{}'.format(self.start, self.end)


class CorefacDatasetContact(models.Model):
    dataset = models.OneToOneField(Dataset)
    email = models.CharField(max_length=100)


class Operator(models.Model):
    user = models.OneToOneField(User)

    def __str__(self):
        return '{} {}'.format(self.user.first_name, self.user.last_name)


class OperatorDataset(models.Model):
    dataset = models.OneToOneField(Dataset)
    operator = models.ForeignKey(Operator)


class ReversePhaseDataset(models.Model):
    dataset = models.OneToOneField(Dataset)
    length = models.CharField(max_length=20)


class Prefractionation(models.Model):
    name = models.CharField(max_length=20)

    def __str__(self):
        return self.name


class PrefractionationDataset(models.Model):
    dataset = models.OneToOneField(Dataset)
    prefractionation = models.ForeignKey(Prefractionation)


class HiriefDataset(models.Model):
    pfdataset = models.OneToOneField(PrefractionationDataset)
    hirief = models.ForeignKey(HiriefRange)


class PrefractionationLength(models.Model):
    pfdataset = models.OneToOneField(PrefractionationDataset)
    length = models.CharField(max_length=20)


class PrefractionationFractionAmount(models.Model):
    pfdataset = models.OneToOneField(PrefractionationDataset)
    fractions = models.IntegerField()


class DatasetJob(models.Model):
    dataset = models.ForeignKey(Dataset)
    job = models.ForeignKey(Job)
