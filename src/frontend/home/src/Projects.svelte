<script>

import {querystring, push} from 'svelte-spa-router';
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'
import Table from './Table.svelte'
import Tabs from './Tabs.svelte'
import Details from './ProjectDetails.svelte'
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
  {id: 'datasets', name: '', help: 'Datasets', type: 'icon', icon: 'clipboard-list', multi: false, links: 'dset_ids', linkroute: '#/datasets'},
  {id: 'ptype', name: 'Type', type: 'str', multi: false},
  {id: 'start', name: 'Registered', type: 'str', multi: false},
  {id: 'lastactive', name: 'Last active', type: 'str', multi: false},
];

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
    <p><span class="has-text-weight-bold">Owners:</span> ${resp.owners.join(', ')}</p>
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

async function mergeProjects() {
  const resp = await postJSON('datasets/merge/projects/', {
    projids: selectedProjs,
  });
  if (!resp.ok) {
    const msg = `Something went wrong trying to rename the file: ${resp.error}`;
    notif.errors[msg] = 1;
    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
  } else {
    items[fnid].filename = newname;
    const msg = `Queued file for renaming to ${newname}`;
    notif.messages[msg] = 1;
    setTimeout(function(msg) { notif.messages[msg] = 0 } , flashtime, msg);
  }
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
  {#if selectedProjs.length>1}
  <a class="button" title="Merge projects to sinlge (earliest) project" on:click={mergeProjects}>Merge projects</a>
  {:else}
  <a class="button" title="Merge projects to single (earliest) project" disabled>Merge projects</a>
  {/if}
{:else}
<a class="button" title="Move projects to cold storage (delete)" disabled>Retire projects</a>
<a class="button" title="Move projects to active storage (undelete)" disabled>Reactivate projects</a>
<a class="button" title="PERMANENTLY delete projects from active and cold storage" disabled>Purge projects</a>
<a class="button" title="Merge projects to single (earliest) project" disabled>Merge projects</a>
{/if}

<Table tab="Projects" bind:treatItems={treatItems} bind:notif={notif} bind:selected={selectedProjs} fetchUrl="/show/projects" findUrl="/find/projects" getdetails={getProjDetails} fixedbuttons={fixedbuttons} fields={tablefields} inactive={inactive} on:detailview={showDetails} />

{#if detailsVisible}
<Details closeWindow={() => {detailsVisible = false}} projId={detailsVisible} />
{/if}
