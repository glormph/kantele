import { axisBottom, axisLeft } from 'd3-axis';

export function drawGridLines(yScaleValues, ticknrs, width, plotgroup) {
  // Grid lines on y-axis
  let yGrid = axisLeft(yScaleValues)
    .ticks(ticknrs)
    .tickSize(-width)
    .tickSizeOuter(0)
    .tickFormat('')
  ;
  plotgroup.append('g')
    .attr('class', 'gridlines')
    .attr("transform", "translate(-10, 0)")
    .call(yGrid)
    .selectAll('.tick')
    .select('line')
    .style('stroke', 'lightgrey')
  ;
  // Remove bottom grid/tickline
  plotgroup.select('.gridlines')
    .select('.tick ')
    .attr('opacity', 0)
} 
