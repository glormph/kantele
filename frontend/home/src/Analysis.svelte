<script>

import {querystring, push} from 'svelte-spa-router';
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'
import Table from './Table.svelte'
import Tabs from './Tabs.svelte'
import { flashtime } from '../../util.js'

let selectedAnalyses = [];
let errors = [];

const tablefields = [
  {id: 'jobstate', name: '__hourglass-half', type: 'state', multi: false, links: 'jobid', linkroute: '#/jobs'},
  {id: 'name', name: 'Analysis name', type: 'str', multi: false},
  {id: 'files', name: '', help: 'Input files', type: 'icon', icon: 'database', multi: false, links: 'fn_ids', linkroute: '#/files'},
  {id: 'datasets', name: '', help: 'Datasets', type: 'icon', icon: 'clipboard-list', multi: false, links: 'dset_ids', linkroute: '#/datasets'},
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

async function getAnalysisDetails(anaId) {
	const resp = await getJSON(`/show/analysis/${anaId}`);
  const links = resp.servedfiles.map(([link, name]) => { return `<div><a href="analysis/showfile/${link}" target="_blank">${name}</a></div>`}).join('\n');
  return `
    <p><span class="has-text-weight-bold">Workflow version:</span> ${resp.wf.update}</p>
    <p>${resp.nrfiles} raw files from ${resp.nrdsets} dataset(s) analysed</p>
    <p><span class="has-text-weight-bold">Quant type:</span> ${resp.quants.join(', ')}</p>
    <p>${links}</p>
    <p><span class="has-text-weight-bold">Last lines of log:</span></p>
    <p class="is-family-monospace">${resp.log.join('<br>')}</p>
  `;
}

function deleteAnalyses() {
}

</script>

<Tabs tabshow="Analyses" errors={errors} />

{#if selectedAnalyses.length}
{/if}

<Table tab="Analyses" bind:errors={errors} bind:selected={selectedAnalyses} fetchUrl="/show/analyses" findUrl="/find/analyses" getdetails={getAnalysisDetails} fixedbuttons={[]} fields={tablefields} inactive={['deleted', 'purged']} statecolors={statecolors} />
