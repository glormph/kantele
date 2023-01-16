from django.db import models

from analysis import models as am
from datasets import models as dm


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
    organism = models.ForeignKey(dm.Species, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['gene', 'organism'], name='uni_gene')]


class Protein(models.Model):
    '''A protein name can in theory map to different gene names in 
    different experiments, depending on which input protein data is
    used (e.g.  uniprot/ensembl versions, although not ENSP/ENSG).
    Therefore we have protein/organism and gene/organism, a
    protein/gene/experiment table, and a peptide/protein/experiment table
    Ideally we keep track of protein fasta releases somewhere, like
    we do for Uniprot/ENSEMBL mouse/human, but then we'd still miss 
    a lot of other databases.
    It is also not directly parseable from the pipeline which protein 
    comes from which fasta file, and parsing full fasta files would
    possibly make this table very full in case of proteogenomics
    '''
    name = models.TextField()
    organism = models.ForeignKey(dm.Species, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['name', 'organism'], name='uni_protein')]


class PeptideSeq(models.Model):
    seq = models.TextField(unique=True)


class ProteinGene(models.Model):
    '''A table to connect proteins and genes, since this relationship 
    may not be the same over multiple protein data versions (e.g. 
    ENSEMBL, uniprot). Also if two species share a protein or gene
    name'''
    protein = models.ForeignKey(Protein, on_delete=models.CASCADE)
    gene = models.ForeignKey(Gene, on_delete=models.CASCADE)
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)


class PeptideProtein(models.Model):
    '''Pep can match multiple proteins, to avoid having peptides match
    to irrelevant proteins (e.g. mouse in human experiment) we make this
    table referencing the experiment. Also takes care of changed protein
    names caused by different protein input db versions'''
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



class PSM(models.Model):
    fdr = models.FloatField()
    scan = models.IntegerField()
    # score type in Wfoutput?
    score = models.FloatField()
    # TODO no scan in DIA/TIMS/etc
    # TODO hardcode condition file/scan?
    condition = models.ForeignKey(Condition, on_delete=models.CASCADE)
    peptide = models.ForeignKey(PeptideMolecule, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['condition', 'scan'], name='uni_psmscans')]
