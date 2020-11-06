<script>
import { onMount } from 'svelte';

import Instrument from './Instrument.svelte'
import ProdPlot from './ProdPlot.svelte'
import CFProdPlot from './CFProdPlot.svelte'
import ProjDistPlot from './ProjDistPlot.svelte'

let prodplot;
let cfprodplot;
let projdistplot;


let tabshow = 'prod';
let qcdata = Object.fromEntries(instruments.map(x => [x[1], {loaded: false}]));
let proddata = {
  fileproduction: {},
  projecttypeproduction: {},
};

async function showInst(iid) {
  if (!qcdata[iid].loaded) {
    await getInstrumentQC(iid);
    eval(qcdata[iid].bokeh_code.script);
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
    await getInstrumentQC(iid); eval(qcdata[iid].bokeh_code.script);
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
  setTimeout(() => {
    prodplot.parseData();
    cfprodplot.parseData();
    projdistplot.parseData();
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
    <Instrument bind:bokeh_code={qcdata[instr[1]].bokeh_code} />
    </div>
    {/if}
    {/each}
    <div class={`instrplot ${tabshow === `prod` ? 'active' : 'inactive'}`} >
      <ProdPlot />
    </div>
	</section>
</div>
