<script>
import { createEventDispatcher } from 'svelte';
import Inputfield from './Inputfield.svelte';
import { postJSON } from '../../datasets/src/funcJSON.js'

const dispatch = createEventDispatcher();
  export let meth;

let editing;
let newProtocol;
let newVersion;
let newDOI;
let editingProtocol;
let selectedProtocol = false;
let selectedDisabledProtocol = meth.versions.filter(x => !x.active)[0];


async function editMethod(name, method) {
  const url = 'sampleprep/method/edit/';
  const resp = await postJSON(url, {'newname': name, 'paramopt_id': method.id});
  if (resp.error) {
    dispatch('error', {error: resp.error});
  } else {
    method.name = name;
  }
  editing = false;
}


async function addProtocol() {
  const url = 'sampleprep/version/add/';
  const resp = await postJSON(url, {'doi': newDOI, 'version': newVersion, 'paramopt_id': meth.id});
  if (resp.error) {
    dispatch('error', {error: resp.error});
  } else {
    const newmeth = {id: resp.id, version: newVersion, doi: newDOI, active: true};
    meth.versions.push(newmeth);
    selectedProtocol = newmeth;
  }
  cancelProtocol();
}


async function editProtocol() {
  const url = 'sampleprep/version/edit/';
  const resp = await postJSON(url, {'doi': newDOI, 'version': newVersion, 'prepprot_id': selectedProtocol.id});
  if (resp.error) {
    dispatch('error', {error: resp.error});
  } else {
    selectedProtocol.version = newVersion;
    selectedProtocol.doi = newDOI;
  }
  cancelProtocol();
}


async function archiveProtocol() {
  const url = 'sampleprep/version/disable/';
  const resp = await postJSON(url, {'prepprot_id': selectedProtocol.id});
  if (resp.error) {
    dispatch('error', {error: resp.error});
  } else {
    selectedProtocol.active = false;
    meth.versions = meth.versions;
    selectedProtocol = false;
  }
  cancelProtocol();
}


async function reactivateProtocol() {
  const url = 'sampleprep/version/enable/';
  const resp = await postJSON(url, {'prepprot_id': selectedDisabledProtocol.id});
  if (resp.error) {
    dispatch('error', {error: resp.error});
  } else {
    selectedDisabledProtocol.active = true;
    meth.versions = meth.versions;
    selectedDisabledProtocol = meth.versions.filter(x => !x.active)[0];
  }
  cancelProtocol();
}


async function deleteProtocol() {
  const url = 'sampleprep/version/delete/';
  const resp = await postJSON(url, {'prepprot_id': selectedProtocol.id});
  if (resp.error) {
    dispatch('error', {error: resp.error});
  } else {
    meth.versions = meth.versions.filter(x => x.id !== selectedProtocol.id);
    selectedProtocol = false;
  }
  cancelProtocol();
}


function cancelProtocol() {
  newDOI = '';
  newVersion = '';
  newProtocol = false;
  editingProtocol = false;
}


function startEditProtocol() {
  editingProtocol = true;
  newVersion = selectedProtocol.version;
  newDOI = selectedProtocol.doi;
}


</script>

<div class="box has-background-light">
  <div class="field">
    <label class="label">
      {#if editing}
      <Inputfield intext={meth.name} on:newvalue={e => editMethod(e.detail.text, meth)} />

      {:else}
      <p>
        {meth.name}
        <a title="Edit" on:click={e => editing = true}><i class="has-text-grey fas fa-edit"></i></a>
        <a title="Disable" on:click={e => dispatch('archive', {})}><i class="has-text-grey fas fa-archive"></i></a>
        <a title="Delete" on:click={e => dispatch('delete', {})}><i class="has-text-danger fas fa-trash-alt"></i></a>
      </p>
      <p>
        Versions:
        <a title="New" on:click={e => newProtocol = true}><i class="has-text-grey fas fa-plus"></i></a>
        {#if selectedProtocol}
        <a title="Edit" on:click={startEditProtocol}><i class="has-text-grey fas fa-edit"></i></a>
        <a title="Disable" on:click={archiveProtocol}><i class="has-text-grey fas fa-archive"></i></a>
        <a title="Delete" on:click={deleteProtocol}><i class="has-text-danger fas fa-trash-alt"></i></a>
        {/if}
      </p>

      {/if}
    </label>

    {#if editingProtocol}
    <div class="field">
      <input class="input" type="text" bind:value={newVersion}  placeholder="Your version"/>
      <input class="input" type="text" bind:value={newDOI} placeholder="DOI" />
      <button class="button" on:click={editProtocol}>Update</button>
      <button class="button" on:click={cancelProtocol}>Cancel</button>
    </div>
      {:else if newProtocol}
    <div class="field">
      <input class="input" type="text" bind:value={newVersion} placeholder="Your version"/>
      <input class="input" type="text" bind:value={newDOI} placeholder="DOI" />
      <button class="button" on:click={addProtocol}>Save</button>
      <button class="button" on:click={cancelProtocol}>Cancel</button>
    </div>

    {:else}
    <div class="select">
      <select bind:value={selectedProtocol}>
        <option disabled value={false}>No {meth.name} version</option>
        {#each meth.versions.filter(x => x.active) as version}
        <option value={version}>{version.version} - {version.doi}</option>
        {/each}
      </select>
    </div>
    {/if}
    {#if meth.versions.filter(x => !x.active).length}
    <div class="control mt-4">
      <label class="label">Disabled versions:</label>
      <button on:click={reactivateProtocol} class="icon is-medium"><i class="fas fa-lg fa-undo"></i></button>
      <div class="select is-small ">
        <select bind:value={selectedDisabledProtocol}>
          {#each meth.versions.filter(x => !x.active) as version}
          <option value={version}>{version.version} - {version.doi}</option>
          {/each}
        </select>
      </div>
    </div>
    {/if}
  </div>
</div>
