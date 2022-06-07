export function drawLabels(plot, xlab, ylab, plotheight, plotwidth, axismargin, fontsize) {
  plot.append('text')
   .attr('y', plotheight + 40)
   .attr('x', plotwidth / 2)
   .attr("font-family", "sans-serif")
   .style("text-anchor", "middle")
   .attr("font-size", `${fontsize}px`)
   .text(xlab);

  plot.append('text')
   .attr('y', plotheight / 2)
   .attr('x', 0 - axismargin + fontsize)
   .style("text-anchor", "middle")
   .attr("transform", `rotate(-90 ${0 - axismargin + fontsize} ${plotheight / 2})`)
   .attr("font-family", "sans-serif")
   .attr("font-size", `${fontsize}px`)
   .text(ylab);
}
