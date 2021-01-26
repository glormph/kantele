<script>

import {querystring, push} from 'svelte-spa-router'
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'
import Table from './Table.svelte'
import Tabs from './Tabs.svelte'
import Details from './FileDetails.svelte'
import { flashtime } from '../../util.js'

let selectedFiles = []
let notif = {errors: {}, messages: {}};
let detailsVisible = false;

const tablefields = [
  {id: 'jobs', name: '__hourglass-half', type: 'state', multi: true, links: 'job_ids', linkroute: '#/jobs'},
  {id: 'name', name: 'File', type: 'str', multi: false},
  {id: 'dataset', name: '', type: 'icon', help: 'Dataset', icon: 'clipboard-list', multi: false, links: 'dataset', linkroute: '#/datasets'},
  {id: 'analyses', name: '', type: 'icon', help: 'Analyses', icon: 'cogs', multi: false, links: 'analyses', linkroute: '#/analyses'},
  {id: 'date', name: 'Date', type: 'str', multi: false},
  {id: 'size', name: 'Size', type: 'str', multi: false},
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

function showDetails(event) {
  detailsVisible = event.detail.ids;
}

async function getFileDetails(fnId) {
	const resp = await getJSON(`/show/file/${fnId}`);
  return `
    <p><span class="has-text-weight-bold">Producer:</span> ${resp.producer}</p>
    <p><span class="has-text-weight-bold">Storage location:</span> ${resp.path}</p>
    ${resp.description ? `<p><span class="has-text-weight-bold">Description:</span> ${resp.description}</p>` : ''}
    `;
}

</script>

<Tabs tabshow="Files" notif={notif} />

{#if selectedFiles.length}
<!-- buttons -->
{/if}
  
<Table tab="Files" bind:notif={notif} bind:selected={selectedFiles} fetchUrl="/show/files" findUrl="/find/files" getdetails={getFileDetails} fields={tablefields} inactive={['deleted', 'purged']} statecolors={statecolors} on:detailview={showDetails} />

{#if detailsVisible}
<Details closeWindow={() => {detailsVisible = false}} fnIds={detailsVisible} />
{/if}
