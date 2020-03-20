<script>

import {querystring, push} from 'svelte-spa-router';
import { onMount } from 'svelte';
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'
import Table from './Table.svelte'
import Tabs from './Tabs.svelte'

const tablefields = [
  {id: 'jobs', name: '__hourglass-half', type: 'state', multi: true, links: 'job_ids', linkroute: '#/jobs/?jobids='},
  {id: 'name', name: 'File', type: 'str', multi: false},
  {id: 'dataset', name: '', type: 'icon', help: 'Dataset', icon: 'clipboard-list', multi: false, links: 'dataset', linkroute: '#/datasets/?dsids='},
  {id: 'analyses', name: '', type: 'icon', help: 'Analyses', icon: 'cogs', multi: false, links: 'analyses', linkroute: '#/analyses/?anids='},
  {id: 'date', name: 'Date', type: 'str', multi: false},
  {id: 'backup', name: 'Backed up', type: 'bool', multi: false},
  {id: 'owner', name: 'Belongs', type: 'str', multi: false},
  {id: 'ftype', name: 'Type', type: 'str', multi: false},
];

const statecolors = {
  stored: false,
  jobs: {
    wait: 'has-text-grey-light',
    pending: 'has-text-info',
    error: 'has-text-danger', 
    processing: 'has-text-warning', 
    done: 'has-text-success',
  },
}

let files = {};
let order = [];
let selectedFiles = []
let loadingFiles = false;
let findQueryString = '';
let searchdeleted = false;

async function loadFiles(url) {
  files = {};
  order = [];
  loadingFiles = true;
  const result = await getJSON(url);
	files = result.items;
	order = result.order;
  loadingFiles = false;
}

function fetchFiles(fnids) {
	let url = '/show/files/'
	url = fnids.length ? url + `?fnids=${fnids.join(',')}` : url;
  loadFiles(url);
}

function findFiles() {
  const url = `/find/files?q=${findQueryString}&deleted=${searchdeleted}`;
  loadFiles(url);
}

function findFilesQuery() {
  if (event.keyCode === 13) {
    push(`#/files?q=${findQueryString}&deleted=${searchdeleted}`);
    findFiles();
  }
}

async function getFileDetails(fnId) {
	const resp = await getJSON(`/show/file/${fnId}`);
  return `
    <p><span class="has-text-weight-bold">Producer:</span> ${resp.producer}</p>
    <p><span class="has-text-weight-bold">Storage location:</span> ${resp.path}</p>
    ${resp.description ? `<p><span class="has-text-weight-bold">Description:</span> ${resp.description}</p>` : ''}
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
    // 404 FIXME
    fetchFiles([]);
  }
  if ('fnids' in qs) {
    fetchFiles(qs.fnids.split(','));
  } else if ('q' in qs) {
    searchdeleted = ('deleted' in qs) ? true : false;
    findQueryString = qs.q;
    findFiles();
  } else {
    fetchFiles([]);
  }
})
</script>

<Tabs tabshow="Files" />

<div class="content is-small">
  <input type="checkbox" checked={searchdeleted}>Search deleted files 
  <input class="input is-small" on:keyup={findFilesQuery} bind:value={findQueryString} type="text" placeholder="Type a query and press enter to search files">
  
  {#if selectedFiles.length}
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
  
  <Table bind:selected={selectedFiles} loading={loadingFiles} getdetails={getFileDetails} fields={tablefields} order={order} trs={files} statecolors={statecolors}/>
</div>
