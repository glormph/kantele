<script>

import { onMount } from 'svelte';
import { getJSON, postJSON } from './funcJSON.js'
import Param from './Param.svelte';
import ErrorNotif from './ErrorNotif.svelte';
import { dataset_id } from './stores.js';

export let errors;

let samplepreperrors = [];


let dsinfo = {
  operator_id: '',
  dynamic_rp: false,
  rp_length: '',
  params: [],
  enzymes: [],
  no_enzyme: false,
}

let saved = false;
let edited = false;
$: stored = $dataset_id && !edited && saved;

function editMade() { 
  errors = errors.length ? validate() : [];
  edited = true;
}

export function validate() {
  let comperrors = [];
	if (!dsinfo.no_enzyme && !dsinfo.enzymes.filter.length) {
		comperrors.push('Enzyme selection is required');
	}
	if (!dsinfo.operator_id) {
		comperrors.push('Operator is required');
	}
	if (!dsinfo.dynamic_rp && !dsinfo.rp_length) {
		comperrors.push('Reverse phase is required');
	}
	for (let key in dsinfo.params) {
    if (dsinfo.params[key].model === undefined || dsinfo.params[key].model === '') {
			comperrors.push(dsinfo.params[key].title + ' is required');
		}
	}
  return comperrors;
}

export async function save() {
  samplepreperrors = [];
  errors = validate();
  if (errors.length === 0) { 
    let postdata = {
      dataset_id: $dataset_id,
      enzymes: dsinfo.no_enzyme ? [] : dsinfo.enzymes,
      operator_id: dsinfo.operator_id,
      params: dsinfo.params,
      rp_length: dsinfo.dynamic_rp ? '' : dsinfo.rp_length,
    };
    let url = '/datasets/save/mssampleprep/';
    try {
      const resp = await postJSON(url, postdata);
      fetchData();
    } catch(error) {
      if (error.message === '404') { 
        samplepreperrors = [...samplepreperrors, 'Save dataset before saving MS samples'];
      }
    }
  }
}


async function fetchData() {
  let url = '/datasets/show/mssampleprep/';
  url = $dataset_id ? url + $dataset_id : url;
	const response = await getJSON(url);
  for (let [key, val] of Object.entries(response.dsinfo)) { dsinfo[key] = val; }
  edited = false;
  if (dsinfo.operator_id) {
    saved = true;
  }
}

onMount(async() => {
  fetchData();
})

</script>

<style>
</style>

<h5 class="has-text-primary title is-5">
  {#if stored}
  <i class="icon fas fa-check-circle"></i>
  {:else}
  <i class="icon fas fa-edit"></i>
  {/if}
  MS sample prep 
  <button class="button is-small is-danger has-text-weight-bold" disabled={!edited} on:click={save}>Save</button>
  <button class="button is-small is-info has-text-weight-bold" disabled={!edited} on:click={fetchData}>Revert</button>
</h5>

<ErrorNotif errors={samplepreperrors} />

<div class="field">
  <label class="label">Enzymes</label>
  <input type="checkbox" on:change={editMade} bind:checked={dsinfo.no_enzyme}>No enzyme
  {#if !dsinfo.no_enzyme}
  {#each dsinfo.enzymes as enzyme}
  <div class="control">
    <input on:change={editMade} bind:checked={enzyme.checked} type="checkbox">{enzyme.name}
  </div>
  {/each}
  {/if}
</div>


{#each Object.entries(dsinfo.params) as [param_id, param]}
<Param bind:param={param} on:edited={editMade}/>
{/each}

<button class="button is-small is-danger has-text-weight-bold" disabled={!edited} on:click={save}>Save</button>
<button class="button is-small is-info has-text-weight-bold" disabled={!edited} on:click={fetchData}>Revert</button>
