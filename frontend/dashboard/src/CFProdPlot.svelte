<script>
import { onMount } from 'svelte';
import StackedPlot from './StackedPlot.svelte';
import { schemeSet1 } from 'd3-scale-chromatic';

let plotid = "projecttype_production";
let plot;
let data;
let projtypes;
let xkey;

export let inputData;

export function parseData() {
  data = inputData.data.map(d => Object.assign(d, d.day = new Date(d.day)));
  projtypes = new Set(data.map(d => Object.keys(d)).flat());
  xkey = inputData.xkey;
  // setTimeout since after parsing, the plot component hasnt updated its props
  // if we immediately call plot.plot(), that function will fail with undefined
  setTimeout(() => {
    plot.plot();
  }, 0);
}


</script>

<h5 class="title is-5">Raw file production per project type</h5>
<StackedPlot bind:this={plot} plotid={plotid} colorscheme={schemeSet1} data={data} stackgroups={projtypes} xkey={xkey} xlab="Date" ylab="Raw files (GB)" />
