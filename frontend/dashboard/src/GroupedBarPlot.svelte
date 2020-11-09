<script>
import { onMount } from 'svelte';
import { axisBottom, axisLeft } from 'd3-axis';
import { scaleLinear, scaleLog, scaleOrdinal, scaleTime, scaleBand } from 'd3-scale';
import { select } from 'd3-selection';
import { extent, max, min} from 'd3-array';
import { format } from 'd3-format';
import { stack } from 'd3';

import { plotLegend } from './PlotLegend.js'
import { drawLabels } from './AxisLabels.js'


let color;
let svg;
let plotgroup;

export let colorscheme;
export let data;
export let groups;
export let xkey;
export let sizeconfig = {width: 400, height: 300};
export let yscaletype = 'linear';
export let ylab;
export let xlab;


const scaletypes = {
  time: scaleTime,
  linear: scaleLinear,
  logarithmic: scaleLog,
}

const yscale = scaletypes[yscaletype];
const leftaxismargin = 50;
const margin = {t: 130, right: 30, bottom: 70, left: leftaxismargin};

function setColors(groups) {
  color = scaleOrdinal(colorscheme)
    .domain(groups)
}

export function startplot() {
  svg = select(svg)
    .attr('width', sizeconfig.width + margin.left + margin.right)
    .attr('height', sizeconfig.height + margin.t + margin.bottom);
}

export function plot() {
  svg.select('.plotgroup').remove();
  plotgroup = svg.append("g")
    .attr('class', 'plotgroup')
    .attr("transform", "translate(" + margin.left + "," + margin.t + ")");

  groups.delete(xkey);
  const arr_groups = Array.from(groups);
  setColors(arr_groups);

  const plotdata = data.map(x => arr_groups.map(gr => {return {xval: x[xkey], group: gr, value: x[gr]} }).filter(x => x.value).sort((a,b) => a.value < b.value)).flat();

  const xScaleValues = scaleLinear()
    .domain(extent(data.map(d => d[xkey])))
    .range([0, sizeconfig.width]);

  /*
  const xScaleGroup = scaleBand()
    .domain(arr_groups)
    .range([0, xScaleValues.bandwidth()])
    .padding([0.05])
*/

  const datavals = data.map(d => Object.entries(d).filter(([key, val]) => groups.has(key)).map(([key, val]) => val).reduce((acc, cur) => acc += cur, 0));
  const yScaleValues = yscale()
    .domain(extent(datavals))
    .range([sizeconfig.height, 0]);
  
  const barwidth = sizeconfig.width / data.length;

  plotLegend(svg, arr_groups, color, sizeconfig.width, margin);

  plotgroup.append('g').attr('transform', "translate(0," + sizeconfig.height + ")")
    .call(axisBottom(xScaleValues).ticks(10))
    .selectAll("text")
    .attr("transform", "translate(-10,0)rotate(-45)")
    .style("text-anchor", "end");

  drawLabels(plotgroup, xlab, ylab, sizeconfig.height, sizeconfig.width, leftaxismargin, 12);

  plotgroup.append('g')
    .call(axisLeft(yScaleValues).ticks(10, "s"))
    .attr("transform", "translate(-10,0)")
    .selectAll("text")
    .style("text-anchor", "end");

  plotgroup.selectAll('rect').data(plotdata).enter()
    .append('rect')
    .attr('fill', d => color(d.group))
    .attr('width', barwidth)
    .attr('x', d => xScaleValues(d.xval))
    .attr('y' ,d => yScaleValues(d.value))
    .attr('height', d => sizeconfig.height - yScaleValues(d.value))
}

onMount(async() => {
  startplot();
})
</script>

<div>
  <svg bind:this={svg}></svg>
</div>
