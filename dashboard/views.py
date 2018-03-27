from datetime import datetime
import os
import json

from django.shortcuts import render
from django.http import (HttpResponse, JsonResponse, HttpResponseNotAllowed,
                         HttpResponseForbidden)
from bokeh.embed import components

from jobs.jobs import Jobstates, is_job_retryable
from jobs import models as jmodels
from datasets.models import DatasetJob, DatasetRawFile
from analysis.models import AnalysisError
from rawstatus.models import FileJob, Producer
from dashboard import qcplots, models
from kantele import settings


def dashboard(request):
    instruments = Producer.objects.filter(name__in=['Luke', 'Leia', 'Barbie', 'Velos'])
    return render(request, 'dashboard/dashboard.html',
                  {'instruments': zip([x.name for x in instruments], [x.id for x in instruments]),
                  'instrument_ids': [x.id for x in instruments]})


def fail_longitudinal_qc(data):
    """Called in case task detects QC run too bad to extract data from"""
    AnalysisError.objects.create(message=data['errmsg'], 
                                 analysis_id=data['analysis_id'])
    
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
        old_plots[lpd.shortname] = lpd
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
                oldp.value = qcdata
                oldp.save()


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
    dateddata = get_longitud_qcdata(instrument, settings.LONGQC_NXF_WF_ID)
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


def jsonsetify(lst):
    return [x for x in set(lst)]


def show_jobs(request):
    jobs = {k: {} for k in [Jobstates.DONE, Jobstates.ERROR, Jobstates.PENDING,
                            Jobstates.PROCESSING]}
    task_errors = {x.task.id: x for x in jmodels.TaskError.objects.all()}
    for task in jmodels.Task.objects.select_related('job').exclude(
            job__state=Jobstates.DONE):
        freshjob = {'name': task.job.funcname, 'errors': [],
                    'date': datetime.strftime(task.job.timestamp, '%Y%m%d'),
                    'retry': is_job_retryable(task.job), 'id': task.job.id,
                    'tasks': {'PENDING': 0, 'FAILURE': 0, 'SUCCESS': 0}}
        try:
            errors = [task.job.joberror.message]
        except jmodels.JobError.DoesNotExist:
            errors = []
        try:
            errors.append(task.taskerror.message)
        except jmodels.TaskError.DoesNotExist:
            pass
        if not task.job.state in jobs:
            jobs[task.job.state] = {task.job.id: freshjob}
        elif not task.job.id in jobs[task.job.state]:
            jobs[task.job.state][task.job.id] = freshjob
        jobs[task.job.state][task.job.id]['tasks'][task.state] += 1
        jobs[task.job.state][task.job.id]['errors'] = errors
    for job in jmodels.Job.objects.filter(task__isnull=True).exclude(state=Jobstates.DONE):
        jobs[job.state][job.id] = {'name': job.funcname,
                                   'date': datetime.strftime(job.timestamp, '%Y%m%d'),
                                   'retry': is_job_retryable(job), 'id': job.id,
                                   'tasks': {'PENDING': 0, 'FAILURE': 0, 'SUCCESS': 0}}
    jobs = {state: {j['id']: j for j in taskjobs.values()} for state, taskjobs in jobs.items()}
    fjobmap = {}
    for fj in FileJob.objects.select_related('storedfile__rawfile__producer', 
            'storedfile__rawfile__datasetrawfile__dataset__runname__experiment__project', 'job').exclude(job__state=Jobstates.DONE):
        if not fj.job.id in fjobmap:
            fjobmap[fj.job.id] = []
        fjobmap[fj.job.id].append(fj)
    for job_id, fjobs in fjobmap.items():
        info = {'files': [os.path.join(x.storedfile.servershare.name, x.storedfile.path,
                                       x.storedfile.filename) for x in fjobs]}
        try:
            dsets = jsonsetify([x.storedfile.rawfile.datasetrawfile.dataset for x in fjobs])
            info.update({'users': jsonsetify(['{} {}'.format(x.user.first_name, x.user.last_name) for x in dsets]),
                         'more': ['{} - {} - {}'.format(x.runname.experiment.project.name, x.runname.experiment.name, x.runname.name) for x in dsets]})
        except DatasetRawFile.DoesNotExist:
            info.update({'files': jsonsetify([os.path.join(x.storedfile.servershare.name,
                                                x.storedfile.path, x.storedfile.filename) for x in fjobs]),
                         'users': jsonsetify([x.storedfile.rawfile.producer.name for x in fjobs]), 'more': []})
        jobs[fjobs[0].job.state][job_id].update(info)
    jobs = {state: [j for j in jmap.values()] for state, jmap in jobs.items()}
    return JsonResponse(jobs)
