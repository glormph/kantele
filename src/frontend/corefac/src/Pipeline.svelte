<script>
import { createEventDispatcher } from 'svelte';
import DynamicSelect from '../../datasets/src/DynamicSelect.svelte';
import Inputfield from './Inputfield.svelte';
import { postJSON } from '../../datasets/src/funcJSON.js'

const dispatch = createEventDispatcher();

export let pipe;
export let flattened_protocols;
export let all_enzymes = [];
export let enzymes = [];

let editingName = false;
let selectedStep = {};
let showStepEdit = {};
let no_enzyme = false;
let editMade = false;

no_enzyme = enzymes.length === 0;


function addPipelineStep(ix, step_id) {
  const step = {name: flattened_protocols[step_id].name, id: flattened_protocols[step_id].id};
  pipe.steps.splice(ix, 0, step);
  delete(selectedStep[ix]);
  showStepEdit[ix] = false;
  pipe.steps = pipe.steps.map((x, ix) => {return {...x, ix: ix}});
  editMade = true;
}

function deletePipelineStep(rmix) {
  pipe.steps = pipe.steps.filter((step, ix) => ix !== rmix);
  pipe.steps = pipe.steps.map((x, ix) => {return {...x, ix: ix}});
  editMade = true;
}


async function archivePipeline() {
  const url = 'sampleprep/pipeline/disable/';
  const resp = await postJSON(url, {id: pipe.id})
  if (resp.error) {
    dispatch('error', {error: resp.error});
  } else {
    pipe.active = false;
    dispatch('pipelineupdate', {});
  }
}


async function savePipeline() {
  const url = 'sampleprep/pipeline/edit/';
  const resp = await postJSON(url, {id: pipe.id, version: pipe.version, pipe_id: pipe.pipe_id,
    steps: pipe.steps, enzymes: no_enzyme ? [] : enzymes,
  });
  if (resp.error) {
    dispatch('error', {error: resp.error});
  } else {
    dispatch('pipelineupdate', {});
    editMade = false;
  }
}


async function lockPipeline() {
  console.log('hej');
  // First save pipeline, then lock
  await savePipeline();
  const url = 'sampleprep/pipeline/lock/';
  const resp = await postJSON(url, {id: pipe.id});
  if (resp.error) {
    dispatch('error', {error: resp.error});
  } else {
    dispatch('pipelineupdate', {});
    editMade = false;
    pipe.locked = true;
  }
}


function editName(name) {
  pipe.version = name;
  editingName = false;
  editMade = true;
}

</script>

<div class="box">
  <div class="field">
  <label class="label">
    {#if editingName}
    <Inputfield addIcon={false} intext={pipe.version} on:newvalue={e => editName(e.detail.text)} />
    {:else}
<p>
    {#if pipe.locked}
    <i class="icon fas fa-lock"></i>
    {:else}
      {#if !editMade}
      <i class="icon far fa-save has-text-grey"></i>
      {:else}
      <a title="Save" on:click={savePipeline}>
        <i class="icon far fa-save"></i>
      </a>
      {/if}
    <a title="Disable" on:click={archivePipeline}><i class="icon fas fa-archive"></i></a>
    <a title="Delete" on:click={e => dispatch('deletepipeline', {'id': pipe.id})}><i class="icon fas fa-trash-alt"></i></a>
    <a title="Edit" on:click={e => editingName = true}><i class="icon fas fa-edit"></i></a>
    <a title="Lock" on:click={lockPipeline}><i class="icon fas fa-lock-open"></i></a>
    {/if}
    <span>{pipe.name} - {pipe.version}</span>
    {#if pipe.locked}
    <div class="is-size-7"> 
    Locked at {pipe.timestamp}
    </div>
    {/if}
    {/if}
</label>
  </div>
  
<div class="field">
  <label class="label">Enzymes</label>
  <input type="checkbox" bind:checked={no_enzyme}>No enzyme
  {#if !no_enzyme}
  {#each all_enzymes as enzyme}
  <div class="control">
    <input bind:group={enzymes} value={enzyme.id} type="checkbox">{enzyme.name}
  </div>
  {/each}
  {/if}
</div>

  <div class="is-flex is-justify-content-center">
    <div class="tag is-primary is-medium">Samples arrived</div>
  </div>
  <div class="mt-2 is-flex is-justify-content-center">
    <i class="icon fas fa-arrow-down"></i>
    <a on:click={e => showStepEdit[0] = true}><i class="icon fas fa-plus-square"></i></a>
  </div>

  {#if showStepEdit[0]}
  <DynamicSelect placeholder="Type to add pipeline step" fixedoptions={flattened_protocols} bind:selectval={selectedStep[0]} niceName={x => x.name} on:selectedvalue={e => addPipelineStep(0, selectedStep[0])} />
  {/if}

  {#each pipe.steps as step, ix}
  <div class="is-flex is-justify-content-center">
    <div class="tag is-info is-medium">
      {step.name}
      <button on:click={e => deletePipelineStep(ix)} class="delete is-medium"></button>
    </div>
  </div>

  {#if showStepEdit[ix+1]}
  <DynamicSelect placeholder="Type to add pipeline step" fixedoptions={flattened_protocols} bind:selectval={selectedStep[ix+1]} niceName={x => x.name} on:selectedvalue={e => addPipelineStep(ix + 1, selectedStep[ix+1])} />
  {:else}
  <div class="mt-2 is-flex is-justify-content-center">
    <i class="icon fas fa-arrow-down"></i>
    <a on:click={e => showStepEdit[ix+1] = true}><i class="icon fas fa-plus-square"></i></a>
  </div>
  {/if}
  {/each}

  <div class="is-flex is-justify-content-center">
    <div class="tag is-danger is-medium">Samples in MS queue</div>
  </div>
</div>
