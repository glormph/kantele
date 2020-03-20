<script>

import {querystring, push} from 'svelte-spa-router';
import { onMount } from 'svelte';
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'
import Table from './Table.svelte'
import Tabs from './Tabs.svelte'


const tablefields = [
  {id: 'ptype', name: 'Project type', type: 'str', multi: false},
  {id: 'storestate', name: 'Stored', type: 'tag', multi: false, links: 'fn_ids', linkroute: '#/files/?fnids='},
  {id: 'jobstates', name: '__hourglass-half', type: 'state', multi: true, links: 'jobids', linkroute: '#/jobs?jobids='},
  {id: 'proj', name: 'Project', type: 'str', multi: false},
  {id: 'exp', name: 'Experiment', type: 'str', multi: false},
  {id: 'run', name: 'Run', type: 'str', multi: false},
  {id: 'usr', name: 'Creator', type: 'str', multi: false},
  {id: 'dtype', name: 'Datatype', type: 'str', multi: false},
];

const statecolors = {
  storestate: {
    cold: 'is-info',
    purged: 'is-danger', 
    complete: 'is-success', 
    'active-only': 'is-warning', 
    new: 'is-warning', 
    empty: 'is-light',
    broken: 'is-light',
  },
  jobstates: {
    wait: 'has-text-grey-light',
    pending: 'has-text-info',
    error: 'has-text-danger', 
    processing: 'has-text-warning', 
    done: 'has-text-success',
  },
}

const fixedbuttons = [
  {name: '__edit', alt: 'Show metadata', action: showMeta},
]

let order = [];
let datasets = {};
let loadingDsets = false;
let allowners = {};
let selectedDsets = []
let findQueryString = '';
let searchdeleted = false;

function showMeta(dsid) {
  console.log(dsid);
}

async function loadDatasets(url) {
  datasets = {};
  order = [];
  loadingDsets = true;
  const result = await getJSON(url);
	datasets = result['dsets'];
  order = result['order'];
  loadingDsets = false;
}

function fetchDatasets(dsids) {
	let url = '/show/datasets/'
	url = dsids.length ? url + `?dsids=${dsids.join(',')}` : url;
  loadDatasets(url);
}

function findDatasets() {
  const url = `/find/datasets?q=${findQueryString}&deleted=${searchdeleted}`;
  loadDatasets(url);
}

function findDatasetQuery(event) {
  if (event.keyCode === 13) {
    // Push doesnt reload the component
    push(`#/datasets?q=${findQueryString}&deleted=${searchdeleted}`);
    findDatasets();
  }
}

async function getDsetDetails(dsetId) {
	const resp = await getJSON(`/show/dataset/${dsetId}`);
  return `
    <p><span class="has-text-weight-bold">Storage location:</span> ${resp.storage_loc}</p>
    <p><span class="has-text-weight-bold">Owners:</span> ${Object.values(resp.owners).join(', ')}</p>
    <hr>
    <p>
    ${Object.entries(resp.nrstoredfiles).map(x => {return `<div>${x[1]} stored files of type ${x[0]}</div>`;}).join('')}
    </p>
    `;
}

async function analyzeDatasets() {
  console.log(selectedDsets);
}

async function archiveDataset() {
}

async function reactivateDataset() {
}

async function purgeDatasets() {
}


onMount(async() => {
  let qs;
  try {
    qs = Object.fromEntries($querystring.split('&').map(x => x.split('=')));
  } catch {
    // FIXME 404
    dset_ids = [1520];
    console.log('oh no');
    fetchDatasets();
    return;
  } 
  if ('dsids' in qs) {
    fetchDatasets(qs.dsids.split(','));
  } else if ('q' in qs) {
    searchdeleted = ('deleted' in qs) ? true : false;
    findQueryString = qs.q;
    findDatasets();
  } else {
    fetchDatasets([]);
  }
})
</script>

<Tabs tabshow="Datasets" />

<div class="content is-small">
  <input type="checkbox" checked={searchdeleted}>Search deleted datasets
  <input class="input is-small" on:keyup={findDatasetQuery} bind:value={findQueryString} type="text" placeholder="Type a query and press enter to search datasets">
  
  {#if selectedDsets.length}
  <a class="button" title="Search MS data" on:click={analyzeDatasets}>Analyze datasets</a>
  <a class="button" title="Move datasets to cold storage (delete)" on:click={archiveDataset}>Retire datasets</a>
  <a class="button" title="Move datasets to active storage (undelete)" on:click={reactivateDataset}>Reactivate datasets</a>
  <a class="button" title="PERMANENTLY delete datasets from active and cold storage" on:click={purgeDatasets}>Purge datasets</a>
  {:else}
  <a class="button" title="Search MS data" disabled>Analyze datasets</a>
  <a class="button" title="Move datasets to cold storage (delete)" disabled>Retire datasets</a>
  <a class="button" title="Move datasets to active storage (undelete)" disabled>Reactivate datasets</a>
  <a class="button" title="PERMANENTLY delete datasets from active and cold storage" disabled>Purge datasets</a>
  {/if}
  
  <Table bind:selected={selectedDsets} loading={loadingDsets} getdetails={getDsetDetails} fixedbuttons={fixedbuttons} fields={tablefields} order={order} trs={datasets} statecolors={statecolors}/>

</div>
