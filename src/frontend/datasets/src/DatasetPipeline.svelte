<script>
import { postJSON } from './funcJSON.js'

export let dspipeId;
export let pipeSteps;
export let pipeStepsDone;
export let samplePrepCategories;
export let savedStageDates = {};

let stageDates = savedStageDates;
let today = new Date();
today = today.toISOString().slice(0, 10);


async function saveDate(stage) {
  if (stageDates[stage] !== savedStageDates[stage]) {
    const url = '/datasets/save/mssampleprep/tracking/';
    const resp = await postJSON(url, {stagename: stage, pipelinestep: false,
      pipeline_id: dspipeId, timestamp: stageDates[stage]})
    if (resp.error) {
      // FIXME show an error
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


function saveToday(stage) {
  stageDates[stage] = today;
  saveDate(stage)
}


</script>

<div class="field">
  <button on:click={e => saveToday('SAMPLESREADY')} class="button is-small"><i class="icon fas fa-window-minimize"></i></button>
  <input on:blur={e => saveDate('SAMPLESREADY')} bind:value={stageDates.SAMPLESREADY} class="input" style="width: 200px" type="date" max={today} />
  <span class="tag is-info is-medium">Samples arrived</span>
</div>
<div class="field">
  <button on:click={e => saveToday('PREPSTARTED')} class="button is-small"><i class="icon fas fa-window-minimize"></i></button>
  <input on:change={e => saveDate('PREPSTARTED')} bind:value={stageDates.PREPSTARTED} class="input" style="width: 200px" type="date" />
  <span class="tag is-info is-medium">Sample prep started</span>
</div>

{#each pipeSteps as [param_id, value_id]}
<div class="field">
  <button class="button is-small"><i class="icon fas fa-window-minimize"></i></button>
  <span class="tag is-medium is-primary">{samplePrepCategories[param_id].fields.filter(x => x.value === value_id)[0].text}</span>
  </div>
{/each}

<div class="field">
  <button on:click={e => saveToday('PREPFINISHED')} class="button is-small"><i class="icon fas fa-window-minimize"></i></button>
  <input on:change={e => saveDate('PREPFINISHED')} bind:value={stageDates.PREPFINISHED} class="input" style="width: 200px" type="date" />
  <span class="tag is-info is-medium">Sample prep finished</span>
</div>
<div class="field">
  <button on:click={e => saveToday('MSQUEUED')} class="button is-small"><i class="icon fas fa-window-minimize"></i></button>
  <input on:change={e => saveDate('MSQUEUED')} bind:value={stageDates.MSQUEUED} class="input" style="width: 200px" type="date" />
  <div class="tag is-info is-medium">MS queue</div>
</div>
