<script>
import { onMount } from 'svelte';
import { axisBottom, axisLeft } from 'd3-axis';
import { scaleLinear, scaleOrdinal, scaleTime } from 'd3-scale';
import { schemeSet1 } from 'd3-scale-chromatic';
import { select } from 'd3-selection';
import { extent, max} from 'd3-array';
import { format } from 'd3-format';
import { stack } from 'd3';


async function fetchProduction() {
  const resp = await fetch('/dash/proddata');
  const result = await resp.json();
  data = result.data.map(d => Object.assign(d, d.day = new Date(d.day)));
  instruments = new Set(data.map(d => Object.keys(d)).flat());
  instruments.delete('day');
}

let data;
let instruments;
let color;

const leftaxismargin = 50;
const margin = {t: 30, right: 30, bottom: 70, left: 100 + leftaxismargin};
const width = 660 - margin.left - margin.right;
const height = 400 - margin.t - margin.bottom;
const barwidth = 10;


function setColors(groups) {
  color = scaleOrdinal(schemeSet1)
    .domain(groups)
}

function plotLegend(svg, datagroups) {

  const boxpadding = 10;
  let groups = datagroups.slice();
  groups.reverse();

  let legend = svg.append('g');

  legend.selectAll('text')
    .data(groups.map((x,i) => [x, i]))
    .enter()
    .append('text')
    .text( d => d[0])
    .attr('fill', 'black')
    .attr("font-family", "sans-serif")
    .attr("font-size", "12px")
    .attr('y', d => d[1] * 20 + 10)
    .attr('x', 20);
  // Legend colored squares
  legend.selectAll('rect')
    .data(groups.map((x, i) => [x, i]))
    .enter()
    .append('rect')
    .attr('width', 10)
    .attr('height', 10)
    .attr('fill', d => color(d[0]))
    .attr('y', d => d[1] * 20)
    ;
  // legend placement
  let legendbbox = legend.node().getBBox();
  margin.left = legendbbox.width + 40 + leftaxismargin; // 40 is margin of leg box and space to axis
  let legendheight = margin.t + height / 2 - legendbbox.height / 2;

  // legend box
  svg.append('rect')
    .attr('x', 5).attr('y', legendheight - boxpadding)
    .attr('width', margin.left - leftaxismargin - 2 * boxpadding).attr('height', legendbbox.height + 2 * boxpadding)
    .attr('stroke', 'black')
    .attr('stroke-width', ".5")
    .attr('fill', 'none');
  // Adjust legend placement to vertical center of plot
  legend.attr("transform", "translate(" + 15 + "," + legendheight + ")");

}

function plotit() {
  const arr_groups = Array.from(instruments);
  setColors(arr_groups);

  const xScale = scaleTime()
    .domain(extent(data.map(d => d.day)))
      //.map(d => [d - 1, d + 1]).flat()))
    .range([0, width]);

  const yScale = scaleLinear()
      .domain([0, max(data.map(d => Object.entries(d).filter(([key, val]) => instruments.has(key)).map(([key, val]) => val).reduce((acc, cur) => acc += cur, 0)))])
    .range([height, 0]);
  
  let svg = select('#myplot')
    .append('svg')
    .attr('width', width + margin.left + margin.right)
    .attr('height', height + margin.t + margin.bottom);

  const stackeddata = stack().keys(arr_groups)(data);

  plotLegend(svg, arr_groups);

  let plot = svg.append("g")
    .attr("transform", "translate(" + margin.left + "," + margin.t + ")");

  plot.append('g').attr('transform', "translate(0," + height + ")")
    .call(axisBottom(xScale))
    .selectAll("text")
    .attr("transform", "translate(-10,0)rotate(-45)")
    .style("text-anchor", "end");

  plot.append('g')
    .call(axisLeft(yScale).ticks(10, "s"))
    .attr("transform", "translate(-10,0)")
    .selectAll("text")
    .style("text-anchor", "end");

  plot.selectAll('plotbar').data(stackeddata).enter()
    .append('g').attr('fill', d => color(d.key))
    .selectAll('rect')
    .data(d => d).enter()
    .append('rect')
    .attr('width', barwidth)
    .attr('transform', `translate(-${barwidth / 2}, 0)`)
    .attr('x', d => xScale(d.data.day))
    .attr('y' ,d => yScale(d[1]))
    .attr('height', d => yScale(d[0]) - yScale(d[1]))
}
onMount(async() => {
  await fetchProduction();
  plotit();
});
///////
</script>

<div id="myplot">
</div>
