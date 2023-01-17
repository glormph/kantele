#from django.test import TestCase

from mstulos import models as m
#from kantele.tests import BaseTest


class BaseTC(BaseTest):
    def setUp(self):
        super().setUp()
        self.expn = 'exp1'
        self.token = 'token1234'
        self.exp = m.Experiment.objects.get_or_create(name=self.expn, token=self.token)
        gene1 = m.Gene.objects.get_or_create(name='gene1')
        self.prot1 = m.Protein.objects.get_or_create(name='protein-1')
        m.ProteinGene.objects.get_or_create(protein=prot1, gene=gene1, experiment=self.exp)
        pseq = m.PeptideSeq.objects.get_or_create(seq='IAMAPEPTIDE')
        m.PeptideProtein.objects.get_or_create(peptide=pseq, protein=self.prot1, experiment=self.exp)
        self.pep1 = m.PeptideMolecule.objects.get_or_create(encoded_pep='+123.345IAMAPEPTIDE', sequence=pseq)
        CT = m.Condition.Condtype
        m.Condition.objects.filter(experiment=self.exp).delete()
        self.cond_sam = m.Condition.objects.create(cond_type=CT.SAMPLE, name='sam1', experiment=self.exp)
        self.cond_set = m.Condition.objects.create(cond_type=CT.SAMPLESET, name='sam1', experiment=self.exp)
        self.cond_ch1 = m.Condition.objects.create(cond_type=CT.CHANNEL, name='ch1', experiment=self.exp)
        self.cond_ch2 = m.Condition.objects.create(cond_type=CT.CHANNEL, name='ch2', experiment=self.exp)

    def test_fail(self):
        resp = self.cl.get(self.url)
        self.assertEqual(resp.status_code, 405)
        resp = self.post_json({'token': 'nottoken'})
        self.assertEqual(resp.status_code, 403)


class TestUploadProteins(BaseTC):
    url = '/mstulos/upload/proteins/'

    def test_upload_proteins(self):
        resp = self.post_json({'token': self.token, 'organism_id': self.species.pk,
            'protgenes': [('prot2', 'gene2'), ('prot1', 'gene1'), ('prot3', 'gene2')]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(m.Protein.objects.count(), 3)
        self.assertEqual(m.Gene.objects.count(), 2)
        self.assertEqual(m.ProteinGene.objects.count(), 3)
        rj = resp.json()
        for pn, ppk in [('prot2', 2), ('prot1', 1), ('prot3', 3)]:
            self.assertEqual(rj[pn], ppk)
        self.fail()

    def test_nogenes(self):
        self.fail()


class TestUploadPeptideProteinRelations(BaseTC):
    url = '/mstulos/upload/peptide_proteins/'

    def test_upload_pepprots(self):
        p2, p3 = '+456IAMAPEPTIDE', 'IAMAPEPTIDE'
        resp = self.post_json({'token': self.token, 'pepprots': [
            (self.pep1.encoded_pep, self.pep1.peptideseq.seq, self.prot1.pk),
            (p2, self.pep1.peptideseq.seq, self.prot1.pk),
            (p3, 'ANOTHERONE', self.prot1.pk),
            ]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(m.PeptideMolecule.objects.count(), 3)
        self.assertEqual(m.PeptideSeq.objects.count(), 2)
        self.assertEqual(m.PeptideProtein.objects.count(), 2)
        rj = resp.json()
        self.assertEqual(rj['pep_ids'], {self.pep1: self.pep1.pk, p2: 2, p3: 3})
        self.fail()


class TestUploadPeptides(BaseTC):
    url = '/mstulos/upload/peptides/'

    def test_upload_peptides(self):
        resp = self.post_json({'token': self.token, 'peptides': [{
            'qval': [(self.cond_set.pk, 0.01)], 'psmcount': [(self.cond_set.pk, 3)], 
            'isobaric': [(self.cond_ch1.pk, 100), (self.cond_ch2.pk, 200)],
            'pep_id': self.pep1.pk}]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(m.PeptideFDR.objects.get(peptide=self.pep1, condition=self.cond_set).fdr, 0.01)
        self.assertEqual(m.AmountPSMsPeptide.objects.get(peptide=self.pep1, condition=self.cond_set).value, 3)
        self.assertEqual(m.PeptideIsoQuant.objects.get(peptide=self.pep1, condition=self.cond_ch1).value, 100)
        self.assertEqual(m.PeptideIsoQuant.objects.get(peptide=self.pep1, condition=self.cond_ch2).value, 200)
        self.fail()

    def test_noisobaric(self):
        self.fail()

class TestUploadPSMs(BaseTC):
    url = '/mstulos/upload/psms/'

    def test_upload_psms(self):
        self.fail()


class TestUploadDone(BaseTC):
    url = '/mstulos/upload/done/'

    def test_uploaddone(self):
        self.fail()

