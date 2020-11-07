<script>
import { onMount } from 'svelte';
import { axisBottom, axisLeft } from 'd3-axis';
import { scaleLinear, scaleLog, scaleOrdinal, scaleTime, scaleBand } from 'd3-scale';
import { select } from 'd3-selection';
import { extent, max, min} from 'd3-array';
import { line } from 'd3';

import { drawLabels } from './AxisLabels.js'


let color;
let svg;

export let colorscheme;
export let data;
export let xkey;
export let sizeconfig = {width: 400, height: 300};
export let yscaletype = 'linear';
export let xscaletype = 'time';
export let ylab;
export let xlab;


const scaletypes = {
  time: scaleTime,
  linear: scaleLinear,
  logarithmic: scaleLog,
}

const yscale = scaletypes[yscaletype];
const xscale = scaletypes[xscaletype];
const leftaxismargin = 50;
const margin = {t: 130, right: 30, bottom: 70, left: leftaxismargin};

function setColors(groups) {
  color = scaleOrdinal(colorscheme)
    .domain(groups)
}

export async function plot() {
  const xScaleValues = xscale()
    .domain(extent(data.map(d => d[xkey])))
    .range([0, sizeconfig.width]);

  /*
  const xScaleGroup = scaleBand()
    .domain(arr_groups)
    .range([0, xScaleValues.bandwidth()])
    .padding([0.05])
*/

  const datavals = data.map(d => [d.lower, d.upper]).flat();
  const yScaleValues = yscale()
    .domain(extent(datavals))
    .range([sizeconfig.height, 0]);
  
  svg = select(svg)
    .attr('width', sizeconfig.width + margin.left + margin.right)
    .attr('height', sizeconfig.height + margin.t + margin.bottom);

  const barwidth = sizeconfig.width / data.length;

  let plot = svg.append("g")
    .attr("transform", "translate(" + margin.left + "," + margin.t + ")");

  plot.append('g').attr('transform', "translate(0," + sizeconfig.height + ")")
    .call(axisBottom(xScaleValues).ticks(10))
    .selectAll("text")
    .attr("transform", "translate(-10,0)rotate(-45)")
    .style("text-anchor", "end");

  drawLabels(plot, xlab, ylab, sizeconfig.height, sizeconfig.width, leftaxismargin, 12);

  plot.append('g')
    .call(axisLeft(yScaleValues).ticks(10, "s"))
    .attr("transform", "translate(-10,0)")
    .selectAll("text")
    .style("text-anchor", "end");

  plot.selectAll('rect').data(data).enter()
    .append('rect')
    .attr('fill', 'steelblue')
    .attr('fill-opacity', 0.5 )//d => color(d.group))
    .attr('stroke', 'black')
    .attr('width', barwidth)
    .attr('x', d => xScaleValues(d[xkey]))
    .attr('y' ,d => yScaleValues(d.q3))
    .attr('height', d => yScaleValues(d.q1) - yScaleValues(d.q3))

  plot.selectAll('.upperline').data(data).enter()
    .append('line')
    .attr('class', 'upperline')
    .attr('fill', 'none')
    .attr('stroke', 'black')
    .attr('stroke-width', 2)
    .attr('x1', d => xScaleValues(d[xkey]) + 0.5 * barwidth)
    .attr('y1' ,d => yScaleValues(d.q3))
    .attr('x2', d => xScaleValues(d[xkey]) + 0.5 * barwidth)
    .attr('y2' ,d => yScaleValues(d.upper))

  plot.selectAll('.lowerline').data(data).enter()
    .append('line')
    .attr('class', 'lowerline')
    .attr('fill', 'none')
    .attr('stroke', 'black')
    .attr('stroke-width', 2)
    .attr('x1', d => xScaleValues(d[xkey]) + 0.5 * barwidth)
    .attr('y1' ,d => yScaleValues(d.q1))
    .attr('x2', d => xScaleValues(d[xkey]) + 0.5 * barwidth)
    .attr('y2' ,d => yScaleValues(d.lower))

  plot.selectAll('.median').data(data).enter()
    .append('line')
    .attr('class', 'median')
    .attr('fill', 'none')
    .attr('stroke', 'black')
    .attr('stroke-width', 2)
    .attr('x1', d => xScaleValues(d[xkey]))
    .attr('y1' ,d => yScaleValues(d.q2))
    .attr('x2', d => xScaleValues(d[xkey]) + barwidth)
    .attr('y2' ,d => yScaleValues(d.q2))
}

</script>

<div>
  <svg bind:this={svg}></svg>
</div>
