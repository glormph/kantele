<script>
import { onMount } from 'svelte';
import { axisBottom, axisLeft } from 'd3-axis';
import { scaleLinear, scaleOrdinal, scaleTime } from 'd3-scale';
import { select } from 'd3-selection';
import { extent, max, min} from 'd3-array';
import { stack } from 'd3';

import { plotLegend } from './PlotLegend.js'
import { drawLabels } from './AxisLabels.js'


let color;
let svg;
let plotgroup;

export let colorscheme;
export let data;
export let stackgroups;
export let xkey;
export let sizeconfig = {width: 400, height: 300};
export let xscaletype = 'time';
export let yscaletype = 'linear';
export let ylab;
export let xlab;


const scaletypes = {
  time: scaleTime,
  linear: scaleLinear,
}

const xscale = scaletypes[xscaletype];
const yscale = scaletypes[yscaletype];
const leftaxismargin = 60;
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

  stackgroups.delete(xkey);
  const arr_groups = Array.from(stackgroups);
  setColors(arr_groups);

  const xScaleValues = xscale()
    .domain(extent(data.map(d => d[xkey])))
    .range([0, sizeconfig.width]);

  const datavals = data.map(d => Object.entries(d).filter(([key, val]) => stackgroups.has(key)).map(([key, val]) => val).reduce((acc, cur) => acc += cur, 0));
  const yScaleValues = yscale()
    .domain([0, max(datavals)])
    .range([sizeconfig.height, 0]);
  
  const stackeddata = stack().keys(arr_groups)(data);
  const barwidth = sizeconfig.width / data.length;

  plotLegend(svg, arr_groups, color, sizeconfig.width, margin);

  plotgroup.append('g').attr('transform', "translate(0," + sizeconfig.height + ")")
    .call(axisBottom(xScaleValues))
    .selectAll("text")
    .attr("transform", "translate(-10,0)rotate(-45)")
    .style("text-anchor", "end");

  plotgroup.append('g')
    .call(axisLeft(yScaleValues).ticks(10, "s"))
    .attr("transform", "translate(-10,0)")
    .selectAll("text")
    .style("text-anchor", "end");

  drawLabels(plotgroup, xlab, ylab, sizeconfig.height, sizeconfig.width, leftaxismargin, 12);

  plotgroup.selectAll('plotbar').data(stackeddata).enter()
    .append('g').attr('fill', d => color(d.key))
    .selectAll('rect')
    .data(d => d).enter()
    .append('rect')
    .attr('width', barwidth)
    .attr('transform', `translate(-${barwidth / 2}, 0)`)
    .attr('x', d => xScaleValues(d.data[xkey]))
    .attr('y' ,d => yScaleValues(d[1]))
    .attr('height', d => yScaleValues(d[0]) - yScaleValues(d[1]))

}

onMount(async() => {
  startplot();
})
</script>

<div>
  <svg bind:this={svg}></svg>
</div>
