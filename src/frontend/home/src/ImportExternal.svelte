<script>
import { onMount } from 'svelte';
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'

export let toggleWindow;

let error;
let indir;
let shareId;
let allshares = [];
let dirsaredsets = false;
let dirsfound = [];
let dsets = {};
let instruments = [];
let view = 'rawfiles';

async function initUserUpload() {
  let resp = await getJSON('/files/external/scan/');
  allshares = resp.shares;
  shareId = allshares[0].id;
}

function evalDirsDsets() {
  dirsaredsets = dirsaredsets === false;
  console.log(dirsfound);
  if (dirsaredsets) {
    dirsfound = dirsfound.map(x => Object.assign(x, {dsname: x.dirname.replaceAll('/', '_')}));
  }
  console.log(dirsfound);
}

async function queueImport() {
  const data = { 
    dirname: indir,
    share_id: shareId,
    dsets: Object.values(dsets),
  };
  console.log(data);
  let resp = await postJSON('/files/external/import/', data);
  // API wants:
  // {share_id: int, dirname: top_lvl_dir, dsets: [{'instrument_id': int, 'name': str, 'files': [(path/to/file.raw', ], 
}

async function scanFolders() {
  let resp = await getJSON(`/files/external/scan?dirname=${indir}`);
  dirsfound = resp.dirsfound.map(x => Object.assign({nrraw: x.files.length, dsname: ''}, x));
  instruments = resp.instruments.map(x => {
    return {id: x[0], name: x[1]};
    })
}

function groupDirsToDsets() {
  // After user inputs names, directories are grouped to datasets if applicable
  // API wants:
  // {share_id: int, dirname: top_lvl_dir, dsets: [{'instrument_id': int, 'name': str, 'files': [(path/to/file.raw', ], 
  dsets = {};
  dirsfound.filter(x => x.dsname !== '').forEach(x => {
    if (!(x.dsname in dsets)) {
      dsets[x.dsname] = {
        name: x.dsname,
        instrument_id: instruments[0].id,
        files: [],
      };
    }
    dsets[x.dsname].files = dsets[x.dsname].files.concat(x.files);
  });
  view = 'dsets';
}

function handleKeypress(event) {
  if (event.keyCode === 27) { toggleWindow(); }
}

onMount(async() => {
  initUserUpload();
})
</script>
<svelte:window on:keyup={handleKeypress} />

<div class="modal is-active">
  <div class="modal-background"></div>
  <div class="modal-content">
    <div class="box">
      <h5 class="title is-5">Import external raw files to datasets</h5>
      <div class="field">
        <div class="control">
          Server share name to find data:
          <div class="select">
            <select bind:value={shareId}>
              {#each allshares as {name, id}}
              <option value={id}>{name}</option>
              {/each}
            </select>
          </div>
        </div>
        <div class="control">
          Directory to import from
          <input class="input" type="text" placeholder="Where you have downloaded the data" bind:value={indir}>
        </div>
      </div>
      
      {#if error}
      <div class="has-text-danger">{error}</div>
      {/if}

      {#if indir}
      <a class="button is-small" on:click={scanFolders}>Check directory</a>
      {:else}
      <a class="button is-small" disabled>Check directory</a>
      {/if}
      {#if dirsfound.length && view === 'rawfiles'}
      <hr>
      <h5 class="title is-5">Raw files found in directories
        {#if !dirsfound.filter(x => x.dsname !== '').length}
        <a class="button is-small" disabled>Group directories</a>
        {:else}
        <a class="button is-small" on:click={groupDirsToDsets}>Group directories</a>
        {/if}
      </h5>
      <table class="table">
        <thead>
          <th>Directory</th>
          <th># of raw files</th>
          <th><input class="checkbox" type="checkbox" value={dirsaredsets} on:click={evalDirsDsets} > 1 directory per dataset</th>
        </thead>
        <tbody>
          {#each dirsfound as {dsname, dirname, nrraw, dsinstrument}}
          <tr>
            <td>{dirname}</td>
            <td>{nrraw}</td>
            <td><input class="input" type="text" bind:value={dsname}></td>
          </tr>
          {/each}
        </tbody>
      </table>
      {:else if dirsfound.length && view === 'dsets'}
      <hr>
      <h5 class="title is-5">Datasets
        <a class="button is-small" on:click={e => view = 'rawfiles'}>Previous</a>
        <a class="button is-small is-info" on:click={queueImport}>Import datasets</a>
      </h5>
      <table class="table">
        <thead>
          <th>Dataset</th>
          <th># of raw files</th>
          <th>Instrument</th>
        </thead>
        <tbody>
          {#each Object.values(dsets) as {name, files, instrument_id}}
          <tr>
            <td>{name}</td>
            <td>{files.length}</td>
            <td>
              <div class="select">
                <select bind:value={instrument_id}>
                  {#each instruments as {id, name}}
                  <option value={id}>{name}</option>
                  {/each}
                </select>
              </div>
          </tr>
          {/each}
        </tbody>
      </table>
      {/if}
    </div>
  </div>
  <button on:click={toggleWindow} class="modal-close is-large" aria-label="close"></button>
</div>
