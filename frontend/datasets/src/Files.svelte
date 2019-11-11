<script>

import { onMount } from 'svelte';
import { getJSON, postJSON } from './funcJSON.js'
import { dataset_id, datasetFiles } from './stores.js';

// props, wait they are global??
//export let dataset_id;

let files = {
  newFiles: {},
  dsfn_order: [],
  newfn_order: [],
};


let addedFiles = {};
let removed_files = {};
let findQuery = '';
let allDsSelector = false;
let allNewSelector = false;

async function findFiles(event) {
  if (event.keyCode === 13) {
    console.log('finding');
    const response = await getJSON(`/datasets/find/files?q=${findQuery.split(' ').join(',')}`);
    for (let [key, val] of Object.entries(response)) { files[key] = val; }
  }
}

function isoTime(timestamp) {
  let x = new Date(timestamp);
  return x.toISOString();
}

function selectAllNew() {
  let select_state = allNewSelector === false;
  for (let fnid in files.newFiles) {
    files.newFiles[fnid].checked = select_state;
  }
}

$: changed = Object.keys(addedFiles).length || Object.keys(removed_files).length;
$: selectedFiles = Object.values(files.newFiles).concat(Object.values(removed_files)).filter(fn => fn.checked);

function deleteFile(fnid) {
  if (fnid in $datasetFiles) {
    removed_files[fnid] = $datasetFiles[fnid]
    files.dsfn_order = files.dsfn_order.filter(x => x !== fnid);
  } else if (fnid in addedFiles) {
    addedFiles = Object.fromEntries(Object.entries(addedFiles).filter(x => x[1].id !== fnid));
  }
}

function addFiles() {
  for (let fn of Object.values(removed_files).filter(fn => fn.checked)) {
    fn.checked = false;
    //removed_files = file.removed_files.filter[fn.id] = fn;
    delete(removed_files[fn.id]);
    files.dsfn_order = [fn.id].concat(files.dsfn_order);
    //files.newfn_order = files.newfn_order.filter(fnid => fnid !== fn.id);
  }
  for (let fn of Object.values(files.newFiles).filter(fn => fn.checked)) {
    fn.checked = false;
    addedFiles[fn.id] = fn;
    files.newfn_order = files.newfn_order.filter(fnid => fnid !== fn.id);
    //delete(files.newFiles[fn.id]);
  }
}

async function save() {
  let url = '/datasets/save/files/';
  let postdata = {
    dataset_id: $dataset_id,
    added_files: addedFiles,
    removed_files: removed_files,
  };
  await postJSON(url, postdata);
  fetchFiles();
}

async function fetchFiles() {
  let url = '/datasets/show/files/';
  url = $dataset_id ? url + $dataset_id : url;
	const response = await getJSON(url);
  for (let [key, val] of Object.entries(response)) { files[key] = val; }
  for (let key in $datasetFiles) { delete($datasetFiles[key]); }
  for (let [key, val] of Object.entries(response.datasetFiles)) { $datasetFiles[key] = val; }
  addedFiles = {};
  removed_files = {};
}

onMount(async() => {
  fetchFiles();
});

</script>

<div class="content is-small">
  <input class="input is-small" on:keyup={findFiles} bind:value={findQuery} type="text" placeholder="Type a query and press enter to find analyses">
  <div>Showing {files.newfn_order.length} new files ({selectedFiles.length} selected), {files.dsfn_order.length} files in dataset (incl. {Object.keys(removed_files).length}, excl. {Object.keys(addedFiles).length} added files)</div>
  <div>
    <button on:click={save} class="button is-danger is-small" disabled={!changed}>Save</button>
    <button on:click={fetchFiles} class="button is-info is-small">Revert</button>
    <button on:click={addFiles} class="button is-small" disabled={!selectedFiles.length} >Add selected files</button>
  </div>
  <table class="table">
    <thead>
      <tr>
        <th><input type="checkbox" bind:checked={allNewSelector} on:click={selectAllNew}></th>
        <th></th>
        <th>File</th>
        <th>Date</th>
        <th>Size</th>
        <th>Instrument</th>
      </tr>
    </thead> 
    <tbody>
      
      {#each Object.values(addedFiles).concat(files.dsfn_order.map(x => $datasetFiles[x])) as fn}
      <tr>
        <td><span on:click={e => deleteFile(fn.id)} class="icon is-small has-text-danger"><i class="fas fa-times"></i></span></td>
        <td>
          {#if fn.id in $datasetFiles}
          <span class="icon is-small has-text-primary"><i class="fas fa-database"></i></span>
          {/if}
        </td>
        <td>{fn.name}</td>
        <td>{isoTime(fn.date)}</td>
        <td>{fn.size}MB</td>
        <td>{fn.instrument}</td>
      </tr>
      {/each}
      {#each Object.values(removed_files).concat(files.newfn_order.map(x => files.newFiles[x])) as fn}
      <tr>
        <td>
          <input type="checkbox" bind:checked={fn.checked}>
        </td>
        <td></td>
        <td>{fn.name}</td>
        <td>{isoTime(fn.date)}</td>
        <td>{fn.size}MB</td>
        <td>{fn.instrument}</td>
      </tr>
      {/each}
    </tbody>
  </table>
</div>
