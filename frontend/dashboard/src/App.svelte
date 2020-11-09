<script>
import { onMount } from 'svelte';
import { schemeSet1 } from 'd3-scale-chromatic';

// FIXME todo:
// - project type only local?

import Instrument from './Instrument.svelte'
import StackedPlot from './StackedPlot.svelte';
import GroupedBarPlot from './GroupedBarPlot.svelte'
import DateSlider from './DateSlider.svelte';


let prodplot;
let cfprodplot;
let projdistplot;
let instrumenttabs = {};

let firstday = 0;
let maxdays = 30;
let tabshow = 'prod';

let qcdata = Object.fromEntries(instruments.map(x => [x[1], {loaded: false}]));
['ident', 'psms', 'precursorarea', 'prec_error', 'rt', 'msgfscore', 'fwhm', 'ionmob'].forEach(x => {
  instruments.forEach(inst => {
    qcdata[inst[1]][x] = {data: [], series: [], xkey: false};
  })
});
let proddata = {
  fileproduction: {},
  projecttypeproduction: {},
  projectdistribution: {},
};

async function showInst(iid) {
  if (!qcdata[iid].loaded) {
    await getInstrumentQC(iid, 0, 30);
    instrumenttabs[iid].parseData();
  }
  tabshow = `instr_${iid}`;
}

async function getInstrumentQC(instrument_id, daysago, maxdays) {
  const response = await fetch(`/dash/longqc/${instrument_id}/${daysago}/${maxdays}`);
  const result = await response.json();
  qcdata[instrument_id] = {};
  for (let key in result) {
    qcdata[instrument_id][key] = result[key];
  }
  qcdata[instrument_id].loaded = true;
}

function showProd() {
  tabshow = 'prod';
}

async function reloadInstrument(e) {
  console.log(e);
  qcdata[e.detail.instrument_id].loaded = false;
  await getInstrumentQC(e.detail.instrument_id, e.detail.firstday, e.detail.showdays);
  instrumenttabs[e.detail.instrument_id].parseData();
}

async function fetchProductionData(maxdays, firstday) {
  console.log(firstday, maxdays);
  const resp = await fetch(`/dash/proddata/${firstday}/${maxdays}`);
  proddata = await resp.json();
  // setTimeout since after fetching, the plot components havent updated its props
  proddata.fileproduction.data.map(d => Object.assign(d, d.day = new Date(d.day)));
  proddata.fileproduction.instruments = new Set(proddata.fileproduction.data.map(d => Object.keys(d)).flat());
  proddata.projecttypeproduction.data.map(d => Object.assign(d, d.day = new Date(d.day)));
  proddata.projecttypeproduction.projtypes= new Set(proddata.projecttypeproduction.data.map(d => Object.keys(d)).flat());
  proddata.projectdistribution.ptypes = new Set(proddata.projectdistribution.data.map(d => Object.keys(d)).flat());
  setTimeout(() => {
    prodplot.plot();
    cfprodplot.plot();
    projdistplot.plot();
  }, 0);
}

onMount(async() => {
  fetchProductionData(maxdays, firstday);
})
</script>

<style>
.instrplot.inactive {
  display: none;
}
</style>

<div class="tabs is-toggle is-centered is-small">
	<ul>
    <li class={tabshow === `prod` ? 'is-active' : ''}>
      <a on:click={showProd}><span>Production</span></a>
    </li>
    {#each instruments as instr}
    <li class={tabshow === `instr_${instr[1]}` ? 'is-active' : '' }>
      <a on:click={e => showInst(instr[1])}><span>{instr[0]}</span></a>
    </li>
    {/each}
	</ul>
</div>
<div class="container">
  <section>
    {#each instruments as instr}
    <div class={`instrplot ${tabshow === `instr_${instr[1]}` ? 'active' : 'inactive'}`} >
      <Instrument on:reloaddata={e => reloadInstrument(e)} bind:this={instrumenttabs[instr[1]]} bind:instrument_id={instr[1]} bind:qcdata={qcdata[instr[1]]} />
    </div>
    {/each}
    <div class={`instrplot ${tabshow === `prod` ? 'active' : 'inactive'}`} >
      <DateSlider on:updatedates={e => fetchProductionData(e.detail.showdays, e.detail.firstday)} />
      <hr>
      <div class="tile is-ancestor">
        <div class="tile">
          <div class="content">
<h5 class="title is-5">Raw file production per instrument</h5>
            <StackedPlot bind:this={prodplot} colorscheme={schemeSet1} data={proddata.fileproduction.data} stackgroups={proddata.fileproduction.instruments} xkey={proddata.fileproduction.xkey} xlab="Date" ylab="Raw files (GB)" />
          </div>
        </div>
        <div class="tile">
          <div class="content">
<h5 class="title is-5">Raw file production per project type</h5>
            <StackedPlot bind:this={cfprodplot} colorscheme={schemeSet1} data={proddata.projecttypeproduction.data} stackgroups={proddata.projecttypeproduction.projtypes} xkey={proddata.projecttypeproduction.xkey} xlab="Date" ylab="Raw files (GB)" />
          </div>
        </div>
      </div>
      <div class="tile is-ancestor">
        <div class="tile">
          <div class="content">
            <h5 class="title is-5">Active project size distribution</h5>
            <GroupedBarPlot bind:this={projdistplot} colorscheme={schemeSet1} data={proddata.projectdistribution.data} groups={proddata.projectdistribution.ptypes} xkey={proddata.projectdistribution.xkey} ylab="# Projects" xlab="Raw files (GB)" />
          </div>
        </div>
        <div class="tile">
          <div class="content">

          </div>
        </div>
      </div>
      
    </div>
	</section>
</div>
