<script>

import { createEventDispatcher } from 'svelte';
const dispatch = createEventDispatcher();

// props
export let dsinfo;
export let hirief_ranges;
export let prefracs;

let errors = [];


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
  <label class="label">Number of fractions</label>
  <div class="control">
    <input type="number" class="input" placeholder="How many fractions of prefractionation" on:change={editMade} bind:value={dsinfo.prefrac_amount}>
  </div>
</div>
{/if}
