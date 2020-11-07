const legendBlock = {width: 10, height: 10};
const fontsize = 12;
const legendBoxpadding = 10;

function calculateLegendPosition(textwidths, plotwidth) {
  let legendLines = [];
  let currentlinewidth = legendBoxpadding;
  let curHeight = legendBoxpadding;
  let addedWidth = 0;
  textwidths.forEach(x => {
    addedWidth = legendBlock.width + Math.round(x) + 50;
    if (currentlinewidth + addedWidth <= plotwidth) {
      legendLines.push([currentlinewidth, curHeight]);
      currentlinewidth += addedWidth;
    } else {
      curHeight += fontsize + 8;
      legendLines.push([legendBoxpadding, curHeight]);
      currentlinewidth = legendBoxpadding + addedWidth;
    }
  });
  return legendLines;

}

export function plotLegend(svg, groups, color, plotwidth, margin) {
  groups.reverse();
  let legend = svg.append('g');

  legend.selectAll('text')
    .data(groups.map((x,i) => [x, i]))
    .enter()
    .append('text')
    .text( d => d[0])
    .attr('fill', 'black')
    .attr("font-family", "sans-serif")
    .attr("font-size", `${fontsize}px`)
    .attr('y', d => d[1] * 20 + 10)
    .attr('x', 0);
  
  let legendTextWidths = [];
  legend.selectAll('text')
    .each(function(d, i) {
      let bb = this.getBBox();
      legendTextWidths.push(bb.width)
    });
  const legendLines = calculateLegendPosition(legendTextWidths, plotwidth);
  legend.selectAll('text')
    .data(groups.map((x,i) => i))
    .attr('x', i => legendLines[i][0] + 2 * legendBlock.width)
    .attr('y', i => legendLines[i][1] + legendBlock.height);
    
  // Legend colored squares
  legend.selectAll('rect')
    .data(groups.map((x, i) => [x, i]))
    .enter()
    .append('rect')
    .attr('width', legendBlock.width)
    .attr('height', legendBlock.height)
    .attr('fill', d => color(d[0]))
    .attr('x', d => legendLines[d[1]][0])
    .attr('y', d => legendLines[d[1]][1])
    ;

  // legend placement
  let legendbbox = legend.node().getBBox();
  margin.t = legendbbox.height + 4 * legendBoxpadding;

  // legend box
  svg.append('rect')
    .attr('x', 0).attr('y', 0)
    .attr('width', legendbbox.width + 2 * legendBoxpadding)
    .attr('height', legendbbox.height + 2 * legendBoxpadding)
    .attr('stroke', 'black')
    .attr('stroke-width', ".5")
    .attr('fill', 'none');
}

