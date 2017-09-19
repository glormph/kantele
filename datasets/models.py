from django.db import models
from django.contrib.auth.models import User
from rawstatus.models import RawFile


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


class Datatype(models.Model):
    name = models.TextField(max_length=100)

    def __str__(self):
        return self.name


class Dataset(models.Model):
    user = models.ForeignKey(User)
    date = models.DateTimeField('date created')
    experiment = models.ForeignKey(Experiment)
    datatype = models.ForeignKey(Datatype)


class DatasetRawFile(models.Model):
    dataset = models.ForeignKey(Dataset)
    rawfile = models.OneToOneField(RawFile)


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
    valuename = models.CharField(max_length=100)
    title = models.CharField(max_length=100)


class FieldParameterValue(models.Model):
    dataset = models.ForeignKey(Dataset)
    param = models.ForeignKey(FieldParameter)
    value = models.CharField(max_length=100)
    title = models.CharField(max_length=100)


class Enzyme(models.Model):
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name


class EnzymeDataset(models.Model):
    dataset = models.ForeignKey(Dataset)
    enzyme = models.ForeignKey(Enzyme)


class QuantType(models.Model):
    name = models.CharField(max_length=20)

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


class HiriefDataset(models.Model):
    dataset = models.OneToOneField(Dataset)
    hirief = models.ForeignKey(HiriefRange)


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
