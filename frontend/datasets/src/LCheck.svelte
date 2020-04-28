<script>
import { onMount } from 'svelte';
import { getJSON, postJSON } from './funcJSON.js'
import { dataset_id, datasetFiles, projsamples } from './stores.js';
import ErrorNotif from './ErrorNotif.svelte';
import DynamicSelect from './DynamicSelect.svelte';

export let errors;

let lcerrors = [];
let channelError = {};

let lcdata = {
  quants: {},
  quanttype: '',
  samples: {},
}
let edited = false;

$: Object.keys($datasetFiles).length ? fetchData() : false;

$: foundNewSamples = Object.values(lcdata.samples).some(x => x.newprojsample !== '');
$: stored = $dataset_id && !edited;


function editMade() {
  edited = true;
}

function okChannel(fid) {
  lcdata.samples[fid].badChannel = false;
  editMade();
}

function badChannel(fid) {
  console.log('bad ch');
  console.log(fid);
  lcdata.samples[fid].badChannel = true;
}


async function doSampleSave(ch_or_samfn, ix) { 
  /* Saves a new sample name to the project on backend */
  let postdata = {
    dataset_id: $dataset_id, 
    samplename: ch_or_samfn.newprojsample
  };
  let url = '/datasets/save/projsample/';
  const response = await postJSON(url, postdata);
  // just add the latest projsample, do not just assign the whole projsamples dict, async problems!
  projsamples[response.psid] = response.psname;
  return [response.psid, ix];
}

async function saveNewSamples() {
  /* Goes through each of the new sample names and */
  let saves = [];
  Object.entries(lcdata.samples).filter(x => x[1].newprojsample).forEach(function(samfn) {
    saves.push(doSampleSave(samfn[1], samfn[0]));
  });
  for (let item of saves) {
    let [psid, associd] = await item;
    lcdata.samples[associd].newprojsample = '';
    lcdata.samples[associd].sample = psid;
  }
}

function checkNewSample(file) {
  /* Checks if entered sample is found in project or if it is a new sample */
  let uppername = lcdata.samples[file.associd].newprojsample.trim().toUpperCase();
  let found = Object.entries(projsamples).filter(x=>x[1].name.toUpperCase() == uppername).map(x=>x[0])[0]
  if (found) {
    lcdata.samples[file.associd].sample = parseInt(found);
    lcdata.samples[file.associd].newprojsample = '';
  }
  editMade();
}

function validate() {
  let comperrors = [];
	if (!lcdata.quanttype) {
		comperrors.push('Quant type selection is required');
	}
  for (let fn of Object.values($datasetFiles)) {
    if (!lcdata.samples[fn.associd].sample) {
      comperrors.push('Sample name for each file/channel is required');
    }
    if (!lcdata.samples[fn.associd].channel) {
      comperrors.push('Channel for each file/sample is required');
    }
  }	
  return comperrors;
}

async function save() {
  errors = validate();
  if (!Object.keys($datasetFiles).length) {
    lcerrors = [...lcerrors, 'Add files before saving data'];
  }
  if (errors.length === 0) { 
    let postdata = {
      dataset_id: $dataset_id,
      quanttype: lcdata.quanttype,
      samples: lcdata.samples,
      filenames: Object.values($datasetFiles),
    }
    console.log(postdata);
    const url = '/datasets/save/labelcheck/';
    const response = await postJSON(url, postdata);
    fetchData();
  }
}

async function fetchData() {
  let url = '/datasets/show/labelcheck/';
  url = $dataset_id ? url + $dataset_id : url;
	const response = await getJSON(url);
  for (let [key, val] of Object.entries(response)) { lcdata[key] = val; }
  edited = false;
}

onMount(async() => {
  await fetchData();
})
</script>


<h5 id="labelcheck" class="has-text-primary title is-5">
  {#if stored}
  <i class="icon fas fa-check-circle"></i>
  {:else if edited}
  <i class="icon fas fa-edit"></i>
  {/if}
  Label check
  <button class="button is-small is-danger has-text-weight-bold" disabled={!edited} on:click={save}>Save</button>
  <button class="button is-small is-info has-text-weight-bold" disabled={!edited} on:click={fetchData}>Revert</button>
</h5>

<ErrorNotif errors={lcerrors} />

<div class="field">
  <label class="label">Quant type</label>
  <div class="control">
    <div class="select">
      <select on:change={editMade} bind:value={lcdata.quanttype}>
        <option disabled value="">Please select one</option>
        {#each Object.values(lcdata.quants) as quant}
        <option value={quant.id}>{quant.name}</option>
        {/each}
      </select>
    </div>
  </div>
</div>

{#if foundNewSamples}
<a class="button is-danger is-small is-pulled-right" on:click={saveNewSamples}>Save new samples</a>
{:else}
<a class="button is-danger is-small is-pulled-right" disabled>Save new samples</a>
{/if}

<table class="table is-fullwidth" >
  <thead>
    <tr>
      <th>Sample</th>
      <th>Channel</th>
    </tr>
  </thead>
  {#if Object.keys(lcdata.samples).length}
  <tbody>
    {#each Object.values($datasetFiles) as file}
    {#if file.associd in lcdata.samples}
    <tr>
      <td>
        <label class="label">
          {#if lcdata.samples[file.associd].newprojsample}
          <span class="icon has-text-danger"><i class="fas fa-asterisk"></i></span>
          {/if}
          {file.name}
        </label>
        <div class="field">
          <DynamicSelect bind:intext={lcdata.samples[file.associd].samplename} fixedoptions={projsamples} bind:unknowninput={lcdata.samples[file.associd].newprojsample} bind:selectval={lcdata.samples[file.associd].sample} on:selectedvalue={editMade} on:newvalue={e => checkNewSample(file)} niceName={x => x.name}/>
        </div>
      </td>
      <td>
        <div class="field">
          <div class="control">
            <p class={lcdata.samples[file.associd].badChannel ? 'control has-icons-left': ''}>
            {#if lcdata.quanttype}
            <DynamicSelect bind:intext={lcdata.samples[file.associd].channelname} niceName={x=>x.name} bind:fixedoptions={lcdata.quants[lcdata.quanttype].chans} bind:fixedorder={lcdata.quants[lcdata.quanttype].chanorder} bind:selectval={lcdata.samples[file.associd].channel} on:selectedvalue={e => okChannel(file.associd)} on:illegalvalue={e => badChannel(file.associd)} />

            {#if lcdata.samples[file.associd].badChannel}
        <span class="icon is-left has-text-danger">
          <i class="fas fa-asterisk"></i>
        </span>
            {/if}
            {/if}
            </p>
          </div>
        </div>
      </td>
    </tr>
    {/if}
    {/each}
  </tbody>
  {/if}
</table>
