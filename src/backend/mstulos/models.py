from django.db import models

from analysis import models as am


class Experiment(models.Model):
    name = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    upload_complete = models.BooleanField(default=False)
    token = models.TextField()


class ExpAnalysis(models.Model):
    analysis = models.OneToOneField(am.Analysis, on_delete=models.CASCADE)
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)


class Condition(models.Model):
    class Condtype(models.IntegerChoices):
        SAMPLE = 0, 'Sample'
        SAMPLESET = 1, 'Isobaric sample set'
        FILE = 2, 'File'
        SAMPLEGROUP = 3, 'Sample group'
        FRACTION = 4, 'Fraction'
        CHANNEL = 5, 'Isobaric channel'

    cond_type = models.IntegerField(choices=Condtype.choices)
    name = models.TextField()
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)
    parent_conds = models.ManyToManyField('self', symmetrical=False)


class Modification(models.Model):
    # FIXME need to fill this with unimod data
    mass = models.FloatField()
    unimod_name = models.TextField(unique=True)
    unimod_id = models.IntegerField(unique=True)


class ResidueMod(models.Model):
    residue = models.TextField()
    mod = models.ForeignKey(Modification, on_delete=models.CASCADE)


class Gene(models.Model):
    name = models.TextField(unique=True)


class Protein(models.Model):
    name = models.TextField(unique=True)
    gene = models.ForeignKey(Gene, on_delete=models.CASCADE)

    
class PeptideSeq(models.Model):
    seq = models.TextField(unique=True)


class PeptideProtein(models.Model):
    # A per-experiment peptide-protein relation, since experiments have
    # different proteins (organisms, fasta versions, etc)
    peptide = models.ForeignKey(PeptideSeq, on_delete=models.CASCADE)
    protein = models.ForeignKey(Protein, on_delete=models.CASCADE)
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)


class PeptideMolecule(models.Model):
    encoded_pep = models.TextField(unique=True)
    sequence = models.ForeignKey(PeptideSeq, on_delete=models.CASCADE)


class MoleculeMod(models.Model):
    position = models.IntegerField()
    mod = models.ForeignKey(ResidueMod, on_delete=models.CASCADE)
    molecule = models.ForeignKey(PeptideMolecule, on_delete=models.CASCADE)


class PeptideIsoQuant(models.Model):
    value = models.FloatField()
    # condition will be a CHANNEL
    condition = models.ForeignKey(Condition, on_delete=models.CASCADE)
    peptide = models.ForeignKey(PeptideMolecule, on_delete=models.CASCADE)


class PeptideFDR(models.Model):
    fdr = models.FloatField()
    # TODO hardcode condition as set name? Can be sample also
    condition = models.ForeignKey(Condition, on_delete=models.CASCADE)
    peptide = models.ForeignKey(PeptideMolecule, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['condition', 'peptide'], name='uni_pepfdr')]


class AmountPSMsPeptide(models.Model):
    value = models.IntegerField()
    # TODO hardcode condition as set name? Can be sample also
    condition = models.ForeignKey(Condition, on_delete=models.CASCADE)
    peptide = models.ForeignKey(PeptideMolecule, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['condition', 'peptide'], name='uni_pepnrpsms')]



class PSMFDR(models.Model):
    fdr = models.FloatField()
    scan = models.IntegerField()
    # TODO no scan in DIA/TIMS/etc
    # TODO hardcode condition file/scan?
    condition = models.ForeignKey(Condition, on_delete=models.CASCADE)
    peptide = models.ForeignKey(PeptideMolecule, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['condition', 'scan'], name='uni_psmscans')]
