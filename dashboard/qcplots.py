from datetime import timedelta
from itertools import cycle

from bokeh.palettes import d3
from bokeh.plotting import figure
from bokeh.layouts import row
from bokeh.models import Legend


def boxplotrange(qcdata, qckey, instruments):
    width = timedelta(7)
    plots = []
    for instrument in instruments:
        if instrument not in qcdata:
            continue
        plot = figure(x_axis_type='datetime', height=200, width=300,
                      title=instrument, toolbar_location='above')
        for date, data in qcdata[instrument][qckey].items():
            boxplot(plot, date, data, width, 'blue')
        plots.append(plot)
    return row(*plots)


def boxplot(plot, x, data, width, color='black'):
    plot.segment(x, data['upper'], x, data['q3'], line_width=2,
                 line_color=color)
    plot.segment(x, data['lower'], x, data['q1'], line_width=2,
                 line_color=color)
    plot.rect(x, (data['q3'] + data['q2']) / 2, width,
              (data['q3'] - data['q2']), line_width=2, line_color='black',
              fill_color=color)
    plot.rect(x, (data['q2'] + data['q1']) / 2, width,
              (data['q2'] - data['q1']), line_width=2, line_color='black',
              fill_color=color)


def timeseries_line(qcdata, key, instruments):
    plots = []
    firstplot = False
    legcolors, colors = {}, cycle(d3['Category10'][10])
    for instrument in instruments:
        if instrument not in qcdata:
            continue
        leglines = {}
        plot = figure(x_axis_type='datetime', height=200)
        for key in keys:
            datesorted = sorted(qcdata[instrument][key], key=lambda x: x[0])
            try:
                col = legcolors[key]
            except KeyError:
                col = next(colors)
                legcolors[key] = col
            leglines[key] = plot.line(
                [dpoint[0] for dpoint in datesorted], 
                [dpoint[1] for dpoint in datesorted], color=col)
        if not firstplot:
            firstplot = plot
        plots.append(plot)
    
#    print([(cat, [line]) for cat, line in sorted(leglines.items())])
#    firstplot.add_layout(Legend(items=[(cat, [line]) for cat, line in
#                                       sorted(leglines.items())]), 'left')
    return row(*plots)
