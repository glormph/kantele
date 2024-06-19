from django.db import models

from analysis import models as am
from datasets import models as dm


class Experiment(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    upload_complete = models.BooleanField(default=False)
    # FIXME token must have invalidation time
    token = models.TextField()
    analysis = models.OneToOneField(am.Analysis, on_delete=models.CASCADE)


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
    name = models.TextField()
    organism = models.ForeignKey(dm.Species, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['name', 'organism'], name='uni_gene')]


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


class PeptideSeq(models.Model):
    seq = models.TextField(unique=True)


class PeptideProtein(models.Model):
    '''Pep can match multiple proteins, to avoid having peptides match
    to irrelevant proteins (e.g. mouse in human experiment) we make this
    table referencing the experiment. Also takes care of changed protein
    names caused by different protein input db versions'''
    peptide = models.ForeignKey(PeptideSeq, on_delete=models.CASCADE)
    protein = models.ForeignKey(Protein, on_delete=models.CASCADE)
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)


class ProteinGene(models.Model):
    '''A table to connect proteins and genes, since this relationship 
    may not be the same over multiple protein data versions (e.g. 
    ENSEMBL, uniprot), and not all experiments have genes included.
    Also, two species can share a protein or gene name, etc'''
    pepprot = models.OneToOneField(PeptideProtein, on_delete=models.CASCADE)
    gene = models.ForeignKey(Gene, on_delete=models.CASCADE)


class PeptideMolecule(models.Model):
    encoded_pep = models.TextField(unique=True)
    sequence = models.ForeignKey(PeptideSeq, on_delete=models.CASCADE)


class MoleculeMod(models.Model):
    position = models.IntegerField()
    mod = models.ForeignKey(ResidueMod, on_delete=models.CASCADE)
    molecule = models.ForeignKey(PeptideMolecule, on_delete=models.CASCADE)


class IdentifiedPeptide(models.Model):
    setorsample = models.ForeignKey(Condition, on_delete=models.CASCADE)
    peptide = models.ForeignKey(PeptideMolecule, on_delete=models.CASCADE)


class PeptideIsoQuant(models.Model):
    value = models.FloatField()
    channel = models.ForeignKey(Condition, on_delete=models.CASCADE)
    # We can use molecule here instead of identified peptide since we have coupled
    # to a condition which contains the experiment etc
    peptide = models.ForeignKey(PeptideMolecule, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['channel', 'peptide'], name='uni_isochpep')]


class PeptideFDR(models.Model):
    fdr = models.FloatField()
    idpep = models.OneToOneField(IdentifiedPeptide, on_delete=models.CASCADE)


class AmountPSMsPeptide(models.Model):
    # TODO can we merge amountPSM and FDR? PepValues or somethign?
    value = models.IntegerField()
    idpep = models.OneToOneField(IdentifiedPeptide, on_delete=models.CASCADE)


class PSM(models.Model):
    fdr = models.FloatField()
    scan = models.IntegerField()
    # score type in Wfoutput?
    score = models.FloatField()
    # TODO no scan in DIA/TIMS/etc
    # TODO hardcode condition fieldname is file?
    filecond = models.ForeignKey(Condition, on_delete=models.CASCADE)
    peptide = models.ForeignKey(PeptideMolecule, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['filecond', 'scan'], name='uni_psmscans')]
