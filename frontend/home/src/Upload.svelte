<script>

import { onMount } from 'svelte';
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'

export let toggleWindow;

let uploaddesc = '';
let upload_ftypeid;
let uploadError;
let uploadSuccess;
let uploadRunning;
let selectedFile = [];
let ftypes = {};
let waiting = false;

async function getUploadableFiletypes() {
  const resp = await getJSON('/files/upload/userfile');
  ftypes = resp.upload_ftypes;
}

async function uploadFile() {
  waiting = true;
  uploadRunning = true;
  uploadError = uploadSuccess = false;
  let fdata = new FormData();
  fdata.append('file', selectedFile[0]);
  fdata.append('desc', uploaddesc);
  fdata.append('ftype_id', upload_ftypeid);
  let resp = await fetch('/files/upload/userfile/', {
    method: 'POST',
    body: fdata,
    credentials: 'same-origin',
  })
  if (!resp.ok) {
    uploadError = 'Something went wrong trying to send file to server, contact admin';
    return;
  } else {
    resp = await resp.json();
  }
  if ('error' in resp) {
    uploadRunning = uploadSuccess = false;
    uploadError = resp.error;
  } else {
    uploadSuccess = resp.success;
  }
  waiting = false;
}

function handleKeypress(event) {
  if (event.keyCode === 27) { toggleWindow(); }
}

onMount(async() => {
  getUploadableFiletypes()
});
</script>

<svelte:window on:keyup={handleKeypress} />

<div class="modal is-active">
  <div class="modal-background"></div>
  <div class="modal-content">
    <div class="box">
      <h5 class="title is-5">Upload FASTA files</h5>
      <div class="field">
        <div class="file has-name is-fullwidth">
          <label class="file-label">
            {#if waiting}
            <input files={selectedFile} class="file-input" disabled type="file" > 
            {:else}
            <input bind:files={selectedFile} class="file-input" type="file" > 
            {/if}
            <span class="file-cta">
              <span class="file-icon">
                <i class="fas fa-upload"></i>
              </span>
              {#if waiting}
              <span class="file-label">Uploading file...</span>
              {:else}
              <span class="file-label">Choose a file...</span>
              {/if}
            </span>
            <span class="file-name">
              {#if uploadSuccess}
              <span class="has-icon"><i class="fa fa-check has-text-success"></i></span>
              {:else if uploadError}
              <span class="has-icon"><i class="fa fa-times has-text-danger"></i></span>
              {:else if uploadRunning}
              <span class="has-icon"><i class="fa fa-spinner fa-spin"></i></span>
              {/if}
              {#if selectedFile.length}
              {selectedFile[0].name}
              {/if}
            </span>
          </label>
        </div>
      </div>

      <div class="field">
        <div class="control">
          <div class="select">
            {#if waiting}
            <select disabled value={upload_ftypeid}>
              <option>Select filetype</option>
              {#each Object.keys(ftypes) as ftid}
              <option value={ftid}>{ftypes[ftid]}</option>
              {/each}
            </select>
            {:else}
            <select bind:value={upload_ftypeid}>
              <option>Select filetype</option>
              {#each Object.keys(ftypes) as ftid}
              <option value={ftid}>{ftypes[ftid]}</option>
              {/each}
            </select>
            {/if}
          </div>
        </div>
      </div>
      <div class="field">
        <div class="control">
          {#if waiting}
          <input class="input" disabled value={uploaddesc} type="text" placeholder="Description">
          {:else}
          <input class="input" bind:value={uploaddesc} type="text" placeholder="Description">
          {/if}
        </div>
      </div>
      
      {#if uploadError}
      <div class="has-text-danger">{uploadError}</div>
      {/if}
      {#if selectedFile.length && uploaddesc && upload_ftypeid}
      <a class="button is-small" on:click={uploadFile}>Upload file</a>
      {:else if waiting}
      <a class="button is-small" disabled>Upload file</a>
      {:else}
      <a class="button is-small" disabled>Upload file</a>
      {/if}
    </div>
  </div>
  <button on:click={toggleWindow} class="modal-close is-large" aria-label="close"></button>
</div>
