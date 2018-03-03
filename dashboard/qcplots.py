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
        color = 'lightblue'
        plot = figure(x_axis_type='datetime', height=200, width=300,
                      title=instrument, toolbar_location='above')
        qcd = qcdata[instrument][qckey]
        xs = [date for date in qcd]
        ups = [qcd[x]['upper'] for x in xs]
        lows = [qcd[x]['lower'] for x in xs]
        q3s= [qcd[x]['q3'] for x in xs]
        q2s = [qcd[x]['q2'] for x in xs]
        q1s = [qcd[x]['q1'] for x in xs]
        plot.segment(xs, ups, xs, q3s, line_width=2, line_color=color)
        plot.segment(xs, lows, xs, q1s, line_width=2, line_color=color)
        plot.vbar(xs, width, q2s, q3s, line_width=2, line_color='black', fill_color=color)
        plot.vbar(xs, width, q1s, q2s, line_width=2, line_color='black', fill_color=color)
        plots.append(plot)
    return row(*plots)


def timeseries_line(qcdata, keys, instruments):
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
