from django.db import models

from analysis import models as am
from datasets import models as dm
from rawstatus import models as rm


class Experiment(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    upload_complete = models.BooleanField(default=False)
    # FIXME token must have invalidation time
    token = models.TextField()
    analysis = models.OneToOneField(am.Analysis, on_delete=models.CASCADE)
    wfoutput_found = models.ForeignKey(am.WfOutput, on_delete=models.CASCADE)


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
    mass = models.FloatField()
    # Special case: name==Unknown: save new Mod w name=Unknown:${mass}, uni_id=-1,-2,-3
    unimod_name = models.TextField(unique=True)
    unimod_id = models.IntegerField(unique=True)
    # For analysis GUI: Fill JSON field with [["STY", "var", "labile"], ["C", "fix", "stable"], ...]
    predefined_aa_list = models.JSONField()

    def __str__(self):
        return self.unimod_name


class QuantLabelMod(models.Model):
    # If someone tries to delete the quanttype or the mod, restrict it
    quanttype = models.ForeignKey(dm.QuantType, on_delete=models.RESTRICT)
    mod = models.ForeignKey(Modification, on_delete=models.RESTRICT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['quanttype', 'mod'], name='uni_qtype_mod')]


class AnalysisModSpec(models.Model):
    class Locations(models.IntegerChoices):
        ANY = 0, 'Anywhere'
        NTERM = 1, 'N-term'
        CTERM = 2, 'C-term'

    analysis = models.ForeignKey(am.Analysis, on_delete=models.CASCADE)
    # Multiple residues possible, e.g STY, or * for any
    # otherwise maybe also make integerchoice field
    residue = models.TextField()
    mod = models.ForeignKey(Modification, on_delete=models.CASCADE)
    fixed = models.BooleanField()
    location = models.IntegerField(choices=Locations.choices)


class Gene(models.Model):
    name = models.TextField()
    organism = models.ForeignKey(dm.Species, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['name', 'organism'], name='uni_gene')]


class Protein(models.Model):
    '''A protein name can in theory map to different gene names in 
    different experiments, depending on which input protein data is
    used (e.g.  uniprot/ensembl versions, although not ENSP/ENSG).
    Therefore we have protein/fasta/seq, protein/organism and gene/organism, a
    protein/gene/experiment table, and a peptide/protein/experiment table
    '''
    name = models.TextField()


class ProteinFasta(models.Model):
    '''Tracking protein sequences here. For perf reasons we keep track of which
    fasta they came from, so we wont have to look up the sequence for each insert
    '''
    protein = models.ForeignKey(Protein, on_delete=models.CASCADE)
    fafn = models.ForeignKey(rm.StoredFile, on_delete=models.PROTECT)
    sequence = models.TextField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['protein', 'fafn'], name='uni_prot_fa')]


class PeptideSeq(models.Model):
    '''Just the amino acid sequence without modifications'''
    seq = models.TextField(unique=True)


class PeptideProtein(models.Model):
    '''Pep can match multiple proteins, to avoid having peptides match
    to irrelevant proteins (e.g. mouse in human experiment) we make this
    table referencing the experiment. Also takes care of changed protein
    names caused by different protein input db versions'''
    peptide = models.ForeignKey(PeptideSeq, on_delete=models.CASCADE)
    proteinfa = models.ForeignKey(ProteinFasta, on_delete=models.CASCADE)
    proteinpos = models.IntegerField()
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)


class ProteinGene(models.Model):
    '''A table to connect proteins and genes, since this relationship 
    may not be the same over multiple protein data versions (e.g. 
    ENSEMBL, uniprot), and not all experiments have genes included.
    Also, two species can share a protein or gene name, etc'''
    proteinfa = models.OneToOneField(ProteinFasta, on_delete=models.CASCADE)
    gene = models.ForeignKey(Gene, on_delete=models.CASCADE)


class PeptideMolecule(models.Model):
    encoded_pep = models.TextField(unique=True)
    sequence = models.ForeignKey(PeptideSeq, on_delete=models.CASCADE)


class MoleculeMod(models.Model):
    '''PeptideMolecule stored as encoded_pep like: tmt10plex with phos: IAMAPEPTIDE[0:3,8:1]
    To allow for fast searching. But, we will also store modifications here in case 
    of e.g. aggregate reporting, and maybe the encoding will not be necessary'''
    position = models.IntegerField()
    mod = models.ForeignKey(Modification, on_delete=models.CASCADE)
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


class GeneIsoQuant(models.Model):
    value = models.FloatField()
    channel = models.ForeignKey(Condition, on_delete=models.CASCADE)
    gene = models.ForeignKey(Gene, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['channel', 'gene'], name='uni_isochgene')]


class PeptideMS1(models.Model):
    ms1 = models.FloatField()
    idpep = models.OneToOneField(IdentifiedPeptide, on_delete=models.CASCADE)


class PeptideFDR(models.Model):
    fdr = models.FloatField()
    idpep = models.OneToOneField(IdentifiedPeptide, on_delete=models.CASCADE)


class PeptidePosteriorError(models.Model):
    pep = models.FloatField()
    idpep = models.OneToOneField(IdentifiedPeptide, on_delete=models.CASCADE)


class PSM(models.Model):
    fdr = models.FloatField()
    # FIXME PEP in separate model in case its not there
    pep = models.FloatField()
    scan = models.IntegerField()
    # score type in Wfoutput?
    score = models.FloatField()
    charge = models.IntegerField()
    mz = models.FloatField()
    rt = models.FloatField() # in minutes or seconds? SPECIFY!
    # TODO no scan in DIA/TIMS/etc
    # TODO hardcode condition fieldname is file? - what does it mean?
    filecond = models.ForeignKey(Condition, on_delete=models.CASCADE)
    peptide = models.ForeignKey(PeptideMolecule, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['filecond', 'scan'], name='uni_psmscans')]


class PSMMS1Quant(models.Model):
    psm = models.OneToOneField(PSM, on_delete=models.CASCADE)
    ms1quant = models.FloatField()


