from datetime import timedelta
from itertools import cycle

from bokeh.palettes import d3
from bokeh.plotting import figure
from bokeh.layouts import row
from bokeh.models import Legend


def boxplotrange(qcdata, qckey, instruments):
    width = timedelta(7)
    #plot.title = 'Peptide precursor area'
    plots = []
    for instrument in instruments:
        plot = figure(x_axis_type='datetime', height=200, width=300,
                      title=instrument, toolbar_location='above')
        for qc in qcdata:
            date = qc['date']
            data = qc[instrument][qckey]
            boxplot(plot, date, data, width, 'blue')
        plots.append(plot)
    return row(*plots)


def missedcleavageplot(qcdata, instruments):
    plots, remodeled = [], {}
    for dateddata in qcdata:
        date = dateddata['date']
        for instrument in instruments:
            if instrument not in dateddata:
                continue
            data = dateddata[instrument]['miscleav']
            print(data)
            for key, val in data.items():
                try:
                    remodeled[key][instrument].append((date, val))
                except KeyError:
                    try:
                        remodeled[key][instrument] = [(date, val)]
                    except KeyError:
                        remodeled[key] = {instrument: [(date, val)]}
    # {'3': {'luke': [(20170101, 3), (20170501, 4)], 'leia': ...
    colors = cycle(d3['Category10'][10])
    plot = figure(x_axis_type='datetime', width=350, height=200,
                  title=instruments[0], toolbar_location='above')
    leglines = []
    for key, color in zip(sorted(remodeled.keys()), colors):
        leglines.append(plot.line([x[0] for x in remodeled[key][instruments[0]]],
                                  [x[1] for x in remodeled[key][instruments[0]]],
                                  color=color))
    legend = Legend(items=[(key, [line]) for
                           key, line in zip(remodeled, leglines)])
    plots.append(plot)
    plot.add_layout(legend, 'left')
    for instrument in instruments[1:]:
        plot = figure(x_axis_type='datetime', width=300, height=200,
                      title=instrument, toolbar_location='above')
        for key, color in zip(remodeled, colors):
            plot.line([x[0] for x in remodeled[key][instrument]],
                      [x[1] for x in remodeled[key][instrument]], color=color)
        plots.append(plot)
    return row(*plots)


def boxplot(plot, x, data, width, color='black'):
    plot.segment(x, data['upper'], x, data['q3'], line_width=2, line_color=color)
    plot.segment(x, data['lower'], x, data['q1'], line_width=2, line_color=color)
    plot.rect(x, (data['q3'] + data['q2']) / 2, width, (data['q3'] - data['q2']), line_width=2, line_color='black', fill_color=color)
    plot.rect(x, (data['q2'] + data['q1']) / 2, width, (data['q2'] - data['q1']), line_width=2, line_color='black', fill_color=color)


def timeseries_line(qcdata, key, instruments):
    plot = figure(x_axis_type='datetime', height=300)
    leglines = []
    for instrument, color in zip(instruments, cycle(d3['Category10'][10])):
        leglines.append(plot.line([x['date'] for x in qcdata],
                                  [x[instrument][key] for x in qcdata],
                                  color=color))
    plot.add_layout(Legend(items=[(inst, [line]) for inst, line in
                                  zip(instruments, leglines)]), 'right')
    return plot
