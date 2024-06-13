import requests
from django.core.management.base import BaseCommand

from kantele import settings
from analysis.models import UniProtFasta, EnsemblFasta

from jobs import models as jm
from jobs import jobs as jj
from jobs.jobutil import create_job


class Command(BaseCommand):
    help = 'Queue a job to download fasta files automatically from ENSEMBL and Swissprot'

    def handle(self, *args, **options):
        # First check the releases available:
        r = requests.get(settings.ENSEMBL_API, headers={'Content-type': 'application/json'})
        ens_version = r.json()['release'] if r.ok else ''
        r = requests.get(settings.UNIPROT_API.format(settings.UP_ORGS['Homo sapiens'], ''),
                stream=True)
        up_version = r.headers['X-UniProt-Release'] if r.ok else ''
        dbmods = {'ensembl': EnsemblFasta, 'uniprot': UniProtFasta}
        to_download = {'ensembl': {'Homo sapiens', 'Mus musculus'}, 'uniprot': {
            #'SWISS': {'Homo sapiens', 'Mus musculus'},
            'SWISS_ISOFORMS': {'Homo sapiens', 'Mus musculus'},
            #'REFERENCE': {'Homo sapiens', 'Mus musculus'},
            'REFERENCE_ISOFORMS': {'Homo sapiens', 'Mus musculus'}}}
        for local_ens in EnsemblFasta.objects.filter(version=ens_version):
            to_download['ensembl'].remove(local_ens.organism)
        for local_up in UniProtFasta.objects.filter(version=up_version):
            uptype = UniProtFasta.UniprotClass(local_up.dbtype).name
            if uptype in to_download['uniprot']:
                to_download['uniprot'][uptype].remove(local_up.organism)

        # Queue jobs for downloading if needed
        dljobs = jm.Job.objects.filter(funcname='download_fasta_repos').exclude(state__in=[
            jj.Jobstates.REVOKING, jj.Jobstates.CANCELED])
        for org in to_download['ensembl']:
            ens_jobs = dljobs.filter(kwargs__db='ensembl', kwargs__version=ens_version,
                    kwargs__organism=org)
            if not ens_jobs.count():
                create_job('download_fasta_repos', db='ensembl', version=ens_version,
                        organism=org)
        for dbtype, orgs in to_download['uniprot'].items():
            for org in orgs:
                up_jobs = dljobs.filter(kwargs__db='uniprot', kwargs__version=up_version,
                        kwargs__dbtype=dbtype, kwargs__organism=org)
                if not up_jobs.count():
                    create_job('download_fasta_repos', db='uniprot', version=up_version,
                            dbtype=dbtype, organism=org)
