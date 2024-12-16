<script>
import { createEventDispatcher } from 'svelte';
import { postJSON } from './funcJSON.js'

export let dspipeId;
export let pipeSteps;
export let pipeStepsDone;
export let samplePrepCategories;
export let savedStageDates = {};

const dispatch = createEventDispatcher();

let stageDates = Object.assign({}, savedStageDates);
let today = new Date();
today = today.toISOString().slice(0, 10);


async function saveNodateStep(stage_id) {
  console.log(pipeStepsDone);
  console.log(stage_id);
  if (!pipeStepsDone[stage_id]) {
    const url = '/datasets/save/mssampleprep/tracking/';
    const resp = await postJSON(url, {stagename: false, pipelinestep: stage_id,
      pipeline_id: dspipeId, timestamp: false})
    if (resp.error) {
      dispatch('error', {error: resp.error});
    } else {
      resp.tracked
        .forEach(x => {
          savedStageDates[x[0]] = x[1];
        });
      resp.nodate
        .forEach(x => {
        });
    }
  }
}

async function saveDate(stage) {
  if (stageDates[stage] !== savedStageDates[stage]) {
    const url = '/datasets/save/mssampleprep/tracking/';
    const resp = await postJSON(url, {stagename: stage, pipelinestep: false,
      pipeline_id: dspipeId, timestamp: stageDates[stage]})
    if (resp.error) {
      dispatch('error', {error: resp.error});
    } else {
      resp.tracked
        .forEach(x => {
          savedStageDates[x[0]] = x[1];
        });
      resp.nodate
        .forEach(x => {
          pipeStepsDone[x[0]] = x[1];
        });
    }
  }
}


function saveToday(stage) {
  stageDates[stage] = today;
  saveDate(stage)
}


</script>

<div class="field">
  {#if savedStageDates.SAMPLESREADY}
  <span><i class="icon has-text-success fas fa-check"></i></span>
  {:else}
  <button on:click={e => saveToday('SAMPLESREADY')} class="button">Today</button>
  {/if}
  <input on:blur={e => saveDate('SAMPLESREADY')} bind:value={stageDates.SAMPLESREADY} class="input" style="width: 200px" type="date" max={today} />
  <span class="tag is-info is-medium">Samples arrived</span>
</div>


<div class="field">
  {#if savedStageDates.PREPSTARTED}
  <span><i class="icon has-text-success fas fa-check"></i></span>
  {:else}
  <button on:click={e => saveToday('PREPSTARTED')} class="button">Today</button>
  {/if}
  <input on:change={e => saveDate('PREPSTARTED')} bind:value={stageDates.PREPSTARTED} class="input" style="width: 200px" type="date" />
  <span class="tag is-info is-medium">Sample prep started</span>
</div>

{#each pipeSteps as [param_id, value_id, stage_id]}
<div class="field">
  {#if pipeStepsDone[stage_id]}
  <span><i class="icon has-text-success fas fa-check"></i></span>
  {:else}
  <button on:click={e => saveNodateStep(stage_id)} class="button">Done?</button>
  {/if}
  <span class="tag is-medium is-primary">{samplePrepCategories[param_id].fields.filter(x => x.value === value_id)[0].text}</span>
  </div>
{/each}

<div class="field">
  {#if savedStageDates.PREPFINISHED}
  <span><i class="icon has-text-success fas fa-check"></i></span>
  {:else}
  <button on:click={e => saveToday('PREPFINISHED')} class="button">Today</button>
  {/if}
  <input on:change={e => saveDate('PREPFINISHED')} bind:value={stageDates.PREPFINISHED} class="input" style="width: 200px" type="date" />
  <span class="tag is-info is-medium">Sample prep finished</span>
</div>
<div class="field">
  {#if savedStageDates.MSQUEUED}
  <span><i class="icon has-text-success fas fa-check"></i></span>
  {:else}
  <button on:click={e => saveToday('MSQUEUED')} class="button">Today</button>
  {/if}
  <input on:change={e => saveDate('MSQUEUED')} bind:value={stageDates.MSQUEUED} class="input" style="width: 200px" type="date" />
  <div class="tag is-info is-medium">MS queue</div>
</div>
