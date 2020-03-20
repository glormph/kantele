<script>

import {querystring, push} from 'svelte-spa-router';
import { onMount } from 'svelte';
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'
import Table from './Table.svelte'
import Tabs from './Tabs.svelte'

let analyses = {};
let order = [];
let selectedAnalyses = [];
let loadingAnalyses = false;
let findQueryString = '';
let searchdeleted = false;

const tablefields = [
  {id: 'jobstate', name: '__hourglass-half', type: 'state', multi: false, links: 'jobid', linkroute: '#/jobs?jobids='},
  {id: 'name', name: 'Analysis name', type: 'str', multi: false},
  {id: 'files', name: '', help: 'Files', type: 'icon', icon: 'database', multi: false, links: 'fn_ids', linkroute: '#/files?fnids='},
  {id: 'datasets', name: '', help: 'Datasets', type: 'icon', icon: 'clipboard-list', multi: false, links: 'dset_ids', linkroute: '#/datasets?dsids='},
  {id: 'wf', name: 'Workflow', type: 'str', multi: false, links: 'wflink'},
  {id: 'usr', name: 'Users', type: 'str', multi: false},
  {id: 'date', name: 'Date', type: 'str', multi: false},
];

const statecolors = {
  jobstate: {
    wait: 'has-text-grey-light',
    pending: 'has-text-info',
    error: 'has-text-danger', 
    processing: 'has-text-warning', 
    done: 'has-text-success',
  },
}

async function loadAnalyses(url) {
  analyses = {};
	order = [];
  loadingAnalyses = true;
  const result = await getJSON(url);
  console.log(result);
	analyses = result.items;
	order = result.order;
  loadingAnalyses = false;
}

async function fetchAnalyses(anids) {
	let url = '/show/analyses'
	url = anids.length ? url + `?anids=${anids.join(',')}` : url;
  loadAnalyses(url);
}

function findAnalyses() {
  const url = `/find/analyses?q=${findQueryString}&deleted=${searchdeleted}`;
  loadAnalyses(url);
}

function findAnalysesQuery() {
  if (event.keyCode === 13) {
    push(`#/analyses?q=${findQueryString}&deleted=${searchdeleted}`);
    findAnalyses();
  }
}

async function getAnalysisDetails(anaId) {
	const resp = await getJSON(`/show/analysis/${anaId}`);
  return `
    <p><span class="has-text-weight-bold">Workflow version:</span> ${resp.wf.update}</p>
    <p>${resp.nrfiles} raw files from ${resp.nrdsets} dataset(s) analysed</p>
    <p><span class="has-text-weight-bold">Quant type:</span> ${resp.quants.join(', ')}</p>
    <p><span class="has-text-weight-bold">Last lines of log:</span></p>
    <p class="is-family-monospace">${resp.log.join('<br>')}</p>
  `;
}


onMount(async() => {
  let qs;
  try {
    qs = Object.fromEntries($querystring.split('&').map(x => x.split('=')));
  } catch {
    // 404 FIXME
    fetchAnalyses([]);
  }
  if ('anids' in qs) {
    fetchAnalyses(qs.anids.split(','));
  } else if ('q' in qs) {
    searchdeleted = ('deleted' in qs) ? true : false;
    findQueryString = qs.q;
    findAnalyses();
  } else {
    fetchAnalyses([]);
  }
})
</script>

<Tabs tabshow="Analyses" />

<div class="content is-small">

  <input type="checkbox" checked={searchdeleted}>Search deleted analyses
  <input class="input is-small" on:keyup={findAnalysesQuery} bind:value={findQueryString} type="text" placeholder="Type a query and press enter to search analyses">
  
  <Table bind:selected={selectedAnalyses} loading={loadingAnalyses} order={order} getdetails={getAnalysisDetails} fixedbuttons={[]} fields={tablefields} trs={analyses} statecolors={statecolors}/>
</div>
