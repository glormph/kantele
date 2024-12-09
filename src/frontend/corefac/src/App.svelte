<script>

import { onMount } from 'svelte';
import { flashtime, statecolors, helptexts } from '../../util.js'
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'
import DynamicSelect from '../../datasets/src/DynamicSelect.svelte';
import Inputfield from './Inputfield.svelte';

let notif = {errors: {}, messages: {}, links: {}};

let protocols = cf_init_data.protocols;

let editing = {};

let config = {
  wfid: false,
  wfversion: false,
  analysisname: '',
  editable: true,
  external_results: false,
  external_desc: '',
  jobstate: false,
  upload_token: false,
  flags: [],
  multicheck: [],
  isoquants: {}, // contain both isoquant and sampletable
  fileparams: {},
  inputparams: {},
  multifileparams: {},
}


async function addMethod(name, category_id) {
  const url = 'sampleprep/method/add/';
  const resp = await postJSON(url, {'newname': name, 'param_id': category_id});
  if (resp.error) {
    notif.errors[resp.error] = 1;
  } else {
    protocols[category_id].methods.push({name: name, id: resp.id, versions: []});
    protocols = protocols;
  }
}


async function editMethod(name, method) {
  const url = 'sampleprep/method/edit/';
  const resp = await postJSON(url, {'newname': name, 'paramopt_id': method.id});
  if (resp.error) {
    notif.errors[resp.error] = 1;
  } else {
    method.name = name;
    protocols = protocols;
  }
  editing[method.id] = false;
}


async function archiveMethod(method) {
  const url = 'sampleprep/method/disable/';
  const resp = await postJSON(url, {'paramopt_id': method.id});
  if (resp.error) {
    notif.errors[resp.error] = 1;
  } else {
    method.active = false;
    protocols = protocols;
  }
}


async function activateMethod(method) {
  const url = 'sampleprep/method/enable/';
  const resp = await postJSON(url, {'paramopt_id': method.id});
  if (resp.error) {
    notif.errors[resp.error] = 1;
  } else {
    method.active = true;
    protocols = protocols;
  }
}


async function deleteMethod(method, category_id) {
  const url = 'sampleprep/method/delete/';
  const resp = await postJSON(url, {'paramopt_id': method.id});
  if (resp.error) {
    notif.errors[resp.error] = 1;
    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, resp.error);
  } else {
    protocols[category_id].methods = protocols[category_id].methods.filter(x => x.id != method.id);
  }
}



onMount(async() => {
})
</script>

<style>
.errormsg {
  position: -webkit-sticky;
  position: sticky;
  top: 20px;
  z-index: 50000;
}
</style>

<div class="errormsg">
{#if Object.values(notif.errors).some(x => x === 1)}
<div class="notification is-danger is-light"> 
    {#each Object.entries(notif.errors).filter(x => x[1] == 1).map(x=>x[0]) as error}
    <div>{error}</div>
    {/each}
</div>
{/if}

{#if Object.values(notif.links).some(x => x === 1)}
<div class="notification is-danger is-light errormsg"> 
    {#each Object.entries(notif.links).filter(x => x[1] == 1).map(x=>x[0]) as link}
    <div>Click here: <a target="_blank" href={link}>here</a></div>
    {/each}
</div>
{/if}

{#if Object.values(notif.messages).some(x => x === 1)}
<div class="notification is-success is-light errormsg"> 
    {#each Object.entries(notif.messages).filter(x => x[1] == 1).map(x=>x[0]) as message}
    <div>{message}</div>
    {/each}
</div>
{/if}
</div>

<div class="content">
  <div class="columns">
    <div class="column">
      <div class="box has-background-info-light">

       ILab token
      </div>
      <div class="box has-background-info-light">

       Sample locations 
      </div>
    </div>
    <div class="column">
      <div class="box">
        <h5 class="title is-5">Sample prep protocols</h5>
        {#each Object.values(protocols) as proto}
        <div class="box has-background-info-light">
          <h6 class="title is-6">{proto.title}</h6>
          <Inputfield addIcon={true} title={`${proto.title.toLowerCase()} method`} on:newvalue={e => addMethod(e.detail.text, proto.id)} />
          {#each proto.methods.filter(x => x.active) as meth}
          <div class="field">
            <label class="label">
              {#if editing[meth.id]}
              <Inputfield intext={meth.name} on:newvalue={e => editMethod(e.detail.text, meth)} />
        
              {:else}
              {meth.name}
              <a title="Edit" on:click={e => editing[meth.id] = true}><i class="has-text-grey fas fa-edit"></i></a>
              <a title="Archive" on:click={e => archiveMethod(meth)}><i class="has-text-grey fas fa-archive"></i></a>
              <a title="Delete" on:click={e => deleteMethod(meth, proto.id)}><i class="has-text-danger fas fa-trash-alt"></i></a>
              {/if}
            </label>
            <div class="select">
              <select value={false}>
                <option disabled value={false}>No {meth.name} version</option>
                {#each meth.versions as [version, doi]}
                <option value={1}>{version} - {doi}</option>
                {/each}
              </select>
            </div>
          </div>
          {/each}
          {#if proto.methods.filter(x => !x.active).length}
          <h6 class="title is-6">{proto.title}, disabled</h6>
          {/if}  
          {#each proto.methods.filter(x => !x.active) as meth}
            <p>
              {meth.name}
              <a title="Reactivate" on:click={e => activateMethod(meth)}><i class="has-text-grey fas fa-undo"></i></a>
  </p>
          {/each}

        </div>
        {/each}

      </div>
    </div>
    <div class="column">
      <div class="box has-background-info-light">

       Pipelines 
      </div>
    </div>
  </div>

</div>
