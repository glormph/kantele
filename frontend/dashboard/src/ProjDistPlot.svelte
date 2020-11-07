<script>
import { onMount } from 'svelte';
import GroupedBarPlot from './GroupedBarPlot.svelte';
import { schemeSet1 } from 'd3-scale-chromatic';

let plotid = 'project_distribution';
let data;
let ptypes;
let xkey;
let plot;

export let inputData;

export function parseData() {
  data = inputData.data;
  ptypes = new Set(inputData.data.map(d => Object.keys(d)).flat());
  xkey = inputData.xkey;
  // setTimeout since after parsing, the plot component hasnt updated its props
  // if we immediately call plot.plot(), that function will fail with undefined
  setTimeout(() => {
    plot.plot();
  }, 0);
}

// FIXME all plots in one svelte file, and give possiblity to reload with new data on demand
// when zooming etc?
</script>

<h5 class="title is-5">Active project size distribution</h5>
<GroupedBarPlot bind:this={plot} plotid={plotid} colorscheme={schemeSet1} data={data} groups={ptypes} xkey={xkey} ylab="# Projects" xlab="Raw files (GB)" />
