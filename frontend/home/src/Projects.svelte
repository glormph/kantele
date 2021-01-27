<script>

import {querystring, push} from 'svelte-spa-router';
import { getJSON } from '../../datasets/src/funcJSON.js'
import Table from './Table.svelte'
import Tabs from './Tabs.svelte'
import { flashtime } from '../../util.js'

const inactive = ['inactive'];
let selectedProjs = []
let notif = {errors: {}, messages: {}};
let detailsVisible = false;
let treatItems;
let purgeConfirm;

const tablefields = [
  {id: 'name', name: 'Name', type: 'str', multi: false},
//  {id: 'storestate', name: 'Stored', type: 'tag', multi: false, links: 'fn_ids', linkroute: '#/files/'},
//  {id: 'jobstates', name: '__hourglass-half', type: 'state', multi: true, links: 'jobids', linkroute: '#/jobs'},
  {id: 'ptype', name: 'Type', type: 'str', multi: false},
  {id: 'start', name: 'Registered', type: 'str', multi: false},
  {id: 'lastactive', name: 'Last active', type: 'str', multi: false},
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
]

function showDetails(event) {
  detailsVisible = event.detail.ids;
}


function setConfirm() {
  purgeConfirm = true;
  setTimeout(() => { purgeConfirm = false} , flashtime);
}

async function getProjDetails(projid) {
	const resp = await getJSON(`/show/project/${projid}`);
  return `
    <p><span class="has-text-weight-bold">Storage amount:</span> ${resp.stored_total_xbytes}</p>
    <p><span class="has-text-weight-bold">Owners:</span> ${Object.values(resp.owners).join(', ')}</p>
    <hr>
    ${Object.entries(resp.nrstoredfiles).map(x => {return `<div>${x[1]} stored files of type ${x[0]}</div>`;}).join('')}
    <div>Instrument(s) used: <b>${resp.instruments.join(', ')}</b></div>
    `;
}

function archiveProject() {
  const callback = (proj) => {proj.inactive = true; }
  treatItems('datasets/archive/project/', 'project', 'archiving', callback, selectedProjs);
}

function reactivateProject() {
  const callback = (proj) => {proj.inactive = false; }
  treatItems('datasets/undelete/project/', 'project','reactivating', callback, selectedProjs);
}

function purgeProject() {
  const callback = (proj) => {proj.inactive = true; }
  treatItems('datasets/purge/project/', 'project', 'purging', callback, selectedProjs);
}


</script>

<Tabs tabshow="Projects" notif={notif} />

{#if selectedProjs.length}
<a class="button" title="Move projects to cold storage (delete)" on:click={archiveProject}>Retire projects</a>
<a class="button" title="Move projects to active storage (undelete)" on:click={reactivateProject}>Reactivate projects</a>
  {#if purgeConfirm}
  <a class="button is-danger is-light" title="PERMANENTLY delete projects from active and cold storage" on:click={purgeProject}>Are you sure? Purge projects</a>
  {:else}
  <a class="button" title="PERMANENTLY delete projects from active and cold storage" on:click={setConfirm}>Purge projects</a>
  {/if}
{:else}
<a class="button" title="Move projects to cold storage (delete)" disabled>Retire projects</a>
<a class="button" title="Move projects to active storage (undelete)" disabled>Reactivate projects</a>
<a class="button" title="PERMANENTLY delete projects from active and cold storage" disabled>Purge projects</a>
{/if}

<Table tab="Projects" bind:treatItems={treatItems} bind:notif={notif} bind:selected={selectedProjs} fetchUrl="/show/projects" findUrl="/find/projects" getdetails={getProjDetails} fixedbuttons={fixedbuttons} fields={tablefields} inactive={inactive} statecolors={statecolors} on:detailview="" />
