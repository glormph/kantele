<script>

import { createEventDispatcher } from 'svelte';
const dispatch = createEventDispatcher();

// props
export let dsinfo;
export let experiments;
export let hirief_ranges;
export let prefracs;
export let isNewExperiment;

let errors = [];

function toggle_experiment() {
  isNewExperiment = isNewExperiment === false;
}

$: hiriefselected = prefracs.some(pf => pf.id == dsinfo.prefrac_id && pf.name.toLowerCase().indexOf('hirief') > -1)

function editMade() {
  dispatch('edited');
}

export function validate() {
  errors = [];
	if (hiriefselected && !dsinfo.hiriefrange) {
		errors.push('HiRIEF range is required');
	}
	else if (!hiriefselected && dsinfo.prefrac_id && !dsinfo.prefrac_length) {
		errors.push('Prefractionation length is required');
	}
	if (dsinfo.prefrac_id && !dsinfo.prefrac_amount) {
		errors.push('Prefractionation fraction amount is required');
	}
  return errors;
}

function save() {
  if (!validate) { return }

}

</script>

<div class="field">
  <label class="label">Experiment name
    <a class="button is-danger is-outlined is-small" on:click={toggle_experiment}>
    {#if isNewExperiment}
    Existing experiment
    {:else}
    Create new experiment
    {/if}
    </a>
  </label>
  <div class="control">
    {#if isNewExperiment}
    <input class="input" bind:value={dsinfo.newexperimentname} on:change={editMade} type="text" placeholder="Experiment name">
    {:else}
    <div class="select">
      <select bind:value={dsinfo.experiment_id} on:change={editMade}>
        <option disabled value="">Please select one</option>
        {#each experiments as exp}
        <option value={exp.id}>{exp.name}</option>
        {/each}
      </select>
    </div>
    {/if}
  </div>
</div>

<div class="field">
  <label class="label">Prefractionation</label>
  <div class="control">
    <div class="select">
      <select on:change={editMade} bind:value={dsinfo.prefrac_id}>
        <option value="">None</option>
        {#each prefracs as prefrac}
        <option value={prefrac.id}>{prefrac.name}</option>
        {/each}
      </select>
    </div>
  </div>
</div>

{#if hiriefselected}
<div class="field"> 
  <label class="label">HiRIEF range</label>
  <div class="control">
    <div class="select">
      <select on:change={editMade} bind:value={dsinfo.hiriefrange}>
        <option disabled value="">Please select one</option>
        {#each hirief_ranges as range}
        <option value={range.id}>{range.name}</option>
        {/each}
      </select>
    </div>
  </div>
</div>
{:else if dsinfo.prefrac_id}
<div class="field">
  <label class="label">Prefractionation length</label>
  <div class="control">
    <input type="number" class="input" placeholder="in minutes" on:change={editMade} bind:value={dsinfo.prefrac_length}>
  </div>
</div>
{/if}
{#if dsinfo.prefrac_id}
<div class="field">
  <label class="label">Fraction amount</label>
  <div class="control">
    <input type="number" class="input" placeholder="How many fractions of prefractionation" on:change={editMade} bind:value={dsinfo.prefrac_amount}>
  </div>
</div>
{/if}
