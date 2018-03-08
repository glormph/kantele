from datetime import datetime
import os
import json

from django.shortcuts import render
from django.http import (HttpResponse, JsonResponse, HttpResponseNotAllowed,
                         HttpResponseForbidden)
from bokeh.embed import components

from jobs.jobs import Jobstates, is_job_retryable
from jobs.models import Task
from datasets.models import DatasetJob
from rawstatus.models import FileJob, Producer
from dashboard import qcplots, models
from kantele import settings


def dashboard(request):
    instruments = Producer.objects.filter(name__in=['Luke', 'Leia', 'Barbie', 'Velos'])
    return render(request, 'dashboard/dashboard.html',
                  {'instruments': zip([x.name for x in instruments], [x.id for x in instruments]),
                  'instrument_ids': [x.id for x in instruments]})


def store_longitudinal_qc(data):
    try:
        qcrun = models.QCData.objects.get(rawfile_id=data['rf_id'])
    except models.QCData.DoesNotExist:
        qcrun = models.QCData(rawfile_id=data['rf_id'],
                              analysis_id=data['analysis_id'])
        qcrun.save()
        for plotname, qcdata in data['plots'].items():
            create_newplot(qcrun, qcdata, plotname)
    else:
        update_qcdata(qcrun, data)


def create_newplot(qcrun, qcdata, name):
    if type(qcdata) == dict and 'q1' in qcdata:
        models.BoxplotData.objects.create(shortname=name, qcrun=qcrun,
                                          upper=qcdata['upper'],
                                          lower=qcdata['lower'],
                                          q1=qcdata['q1'], q2=qcdata['q2'],
                                          q3=qcdata['q3'])
    else:
        models.LineplotData.objects.create(qcrun=qcrun, value=qcdata, shortname=name)


def update_qcdata(qcrun, data):
    # FIXME rerun old data on new plots or methods at qc task update --> what happens?
    # also FIXME if no changes in msgf etc do recalculation on the analysed files
    old_plots = {p.shortname: p for p in qcrun.boxplotdata_set.all()}
    for lpd in qcrun.lineplotdata_set.all():
        if lpd.shortname not in old_plots:
            old_plots[lpd.shortname] = [lpd]
        else:
            old_plots[lpd.shortname].append(lpd)
    for plotname, qcdata in data['plots'].items():
        try:
            oldp = old_plots[plotname]
        except KeyError:
            create_newplot(qcrun, qcdata, plotname)
        else:
            if type(qcdata) == dict and 'q1' in qcdata:
                oldp.upper = qcdata['upper']
                oldp.lower = qcdata['lower']
                oldp.q1 = qcdata['q1']
                oldp.q2 = qcdata['q2']
                oldp.q3 = qcdata['q3']
                oldp.save()
            else:
                for op in oldp:
                    op.value = qcdata[plotname]
                    op.save()


def get_longitud_qcdata(instrument, wf_id):
    long_qc = {}
    for qcrun in models.QCData.objects.filter(rawfile__producer=instrument,
                                              analysis__nextflowsearch__nfworkflow=wf_id):
        date = qcrun.rawfile.date
        for lplot in qcrun.lineplotdata_set.all():
            try:
                long_qc[lplot.shortname].append((date, lplot.value))
            except KeyError:
                try:
                    long_qc[lplot.shortname] = [(date, lplot.value)]
                except KeyError:
                    long_qc[lplot.shortname] = {[(date, lplot.value)]}
        for boxplot in qcrun.boxplotdata_set.all():
            bplot = {'q1': boxplot.q1, 'q2': boxplot.q2, 'q3': boxplot.q3,
                     'upper': boxplot.upper, 'lower': boxplot.lower}
            try:
                long_qc[boxplot.shortname][date] = bplot
            except KeyError:
                long_qc[boxplot.shortname] = {date: bplot}
    return long_qc


def show_qc(request, instrument_id):
    """
    QC data:
        Date, Instrument, RawFile, AnalysisResult
    """
    instrument = Producer.objects.get(pk=instrument_id)
    dateddata = get_longitud_qcdata(instrument, settings.QC_WORKFLOW_ID)
    plot = {
        'amount_peptides': qcplots.timeseries_line(dateddata, ['peptides', 'proteins', 'unique_peptides']),
        'amount_psms': qcplots.timeseries_line(dateddata, ['scans', 'psms', 'miscleav1', 'miscleav2']),
        'precursorarea': qcplots.boxplotrange(dateddata, 'peparea'),
        'prec_error': qcplots.boxplotrange(dateddata, 'perror'),
        'msgfscore': qcplots.boxplotrange(dateddata, 'msgfscore'),
        'rt': qcplots.boxplotrange(dateddata, 'rt'),
            }
    script, div = components(plot, wrap_script=False, wrap_plot_info=False)
    return JsonResponse({'bokeh_code': {'script': script, 'div': div}})


def show_jobs(request):
    jobs = {}
    for task in Task.objects.select_related('job').filter(
            job__state__in=[Jobstates.PENDING, Jobstates.PROCESSING,
                        Jobstates.ERROR]):
        freshjob = {'name': task.job.funcname, 
                    'date': datetime.strftime(task.job.timestamp, '%Y%m%d'),
                    'retry': is_job_retryable(task.job), 'id': task.job.id,
                    'tasks': {'PENDING': 0, 'FAILURE': 0, 'SUCCESS': 0}}
        if not task.job.state in jobs:
            jobs[task.job.state] = {task.job.id: freshjob}
        elif not task.job.id in jobs[task.job.state]:
            jobs[task.job.state][task.job.id] = freshjob
        jobs[task.job.state][task.job.id]['tasks'][task.state] += 1
    dsfnjobmap = {}
    for dsj in DatasetJob.objects.select_related(
            'dataset__runname__experiment__project', 'dataset__user',
            'job').exclude(job__state=Jobstates.DONE):
        ds = dsj.dataset
        dsname = '{} - {} - {}'.format(ds.runname.experiment.project.name,
                                       ds.runname.experiment.name,
                                       ds.runname.name)
        if dsj.job_id not in dsfnjobmap:
            dsfnjobmap[dsj.job_id] = {
                'user': '{} {}'.format(ds.user.first_name, ds.user.last_name),
                'alttexts': [dsname]}
        else:
            dsfnjobmap[dsj.job_id]['alttexts'].append(dsname)
    for fnj in FileJob.objects.select_related('storedfile__rawfile__producer', 
            'job').exclude(job__state=Jobstates.DONE):
        fname = os.path.join(fnj.storedfile.servershare.name, fnj.storedfile.path,
                             fnj.storedfile.filename)
        dsfnjobmap[fnj.job_id] = {'user': fnj.storedfile.rawfile.producer.name,
                                  'alttexts': [fname]}
    for jstate in [Jobstates.PENDING, Jobstates.PROCESSING, Jobstates.ERROR]:
        if jstate in jobs:
            jobs[jstate] = [x for x in jobs[jstate].values()]
            for job in jobs[jstate]:
                job.update(dsfnjobmap[job['id']])
    return JsonResponse(jobs)
