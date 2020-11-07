<script>
import { onMount } from 'svelte';
import { schemeSet1 } from 'd3-scale-chromatic';

// FIXME todo:
// - day slider or something)//
// - grouped bar plot (just because we can)
// - project type only local?

import Instrument from './Instrument.svelte'
import StackedPlot from './StackedPlot.svelte';
import GroupedBarPlot from './GroupedBarPlot.svelte'


let prodplot;
let cfprodplot;
let projdistplot;
let instrumenttabs = {};


let tabshow = 'prod';
let qcdata = Object.fromEntries(instruments.map(x => [x[1], {loaded: false}]));
let proddata = {
  fileproduction: {},
  projecttypeproduction: {},
  projectdistribution: {},
};

async function showInst(iid) {
  if (!qcdata[iid].loaded) {
    await getInstrumentQC(iid);
    instrumenttabs[iid].parseData();

  }
  tabshow = `instr_${iid}`;
}

function showProd() {
  tabshow = 'prod';
}

async function reload() {
  if (tabshow.slice(0, 6) === 'instr_') {
    const iid = tabshow.substr(6);
    qcdata[iid].loaded = false;
    await getInstrumentQC(iid);
    instrumenttabs[iid].parseData();
  }
}

async function getInstrumentQC(instr_id) {
  const response = await fetch('/dash/longqc/' + instr_id);
  const result = await response.json();
  qcdata[instr_id] = {};
  for (let key in result) {
    qcdata[instr_id][key] = result[key];
  }
  qcdata[instr_id].loaded = true;
}

async function fetchProductionData() {
  const resp = await fetch('/dash/proddata');
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
  fetchProductionData();
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
  <a class="button is-info is-small" on:click={reload}>Refresh</a>
  <hr>
  <section>
    {#each instruments as instr}
    {#if qcdata[instr[1]].loaded}
    <div class={`instrplot ${tabshow === `instr_${instr[1]}` ? 'active' : 'inactive'}`} >
      <Instrument bind:this={instrumenttabs[instr[1]]} bind:qcdata={qcdata[instr[1]]} />
    </div>
    {/if}
    {/each}
    <div class={`instrplot ${tabshow === `prod` ? 'active' : 'inactive'}`} >
      <div class="tile is-ancestor">
        <div class="tile">
          <div class="content">
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
