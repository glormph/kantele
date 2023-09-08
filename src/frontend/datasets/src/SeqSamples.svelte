<script>
import { onMount } from 'svelte';
import { getJSON, postJSON } from './funcJSON.js'
import Param from './Param.svelte';
import ErrorNotif from './ErrorNotif.svelte';
import DynamicSelect from './DynamicSelect.svelte';
import { dataset_id, datasetFiles, projsamples } from './stores.js';

export let errors;

let preperrors = [];
let edited = false;
let fetchedSpecies = {};

$: stored = $dataset_id && !edited;


function editMade() { 
  errors = errors.length ? validate() : [];
  edited = true; 
}

let prepdata = {
  params: [],
  allspecies: [],
  species: [],
  samples: {},
}

let selectedspecies;
let trysamplenames = '';
let foundNewSamples = false;


function niceSpecies(species) { 
  let nice;
  if (species === undefined) {
    nice = '';
  } else if (species.name) {
    nice = `${species.name}, ${species.linnean}`;
  } else {
    nice = `${species.linnean}`;
  }
  return nice;
}

function removeOrganism(org_id) {
  prepdata.species = prepdata.species.filter(x => x.id !== org_id);
  editMade();
}

function addOrganism() {
  const species = (selectedspecies in prepdata.allspecies) ? prepdata.allspecies[selectedspecies] : fetchedSpecies[selectedspecies];
  prepdata.species = [...prepdata.species, species];
  editMade();
}

function checkSamplesIfNewFiles() {
  const assocs = Object.values($datasetFiles).map(x => x.associd);
  prepdata.samples = Object.fromEntries(Object.entries(prepdata.samples).filter(x => assocs.indexOf(Number(x[0])) > -1));
  for (let associd of assocs.filter(x => !(x in prepdata.samples))) {
    prepdata.samples[associd] = {model: '', newprojsample: ''};
  }
}

$: $datasetFiles ? checkSamplesIfNewFiles() : '';

function checkIfNewSamples() {
  /* checks if ANY sample in current quanttype is a newprojectsample, enabling save button */
  foundNewSamples = Object.values(prepdata.samples).some(x => x.newprojsample !== '')
}

function checkNewSampleLabelfree(associd=false) {
  /* Checks if entered sample is found in project or if it is a new sample */
  let sample = prepdata.samples[associd].newprojsample;
  if (sample == '') { 
    return 
  } else {
    let uppername = sample.trim().toUpperCase();
    let found = Object.entries(projsamples).filter(x=>x[1].name.toUpperCase() == uppername).map(x=>x[0])[0]
    if (found) {
      prepdata.samples[associd].model = found;
      prepdata.samples[associd].newprojsample = '';
      /* new samples filled in will reset the dropdown ones, do not do this, only on save */
    }
    checkIfNewSamples();
  }
}

function parseSampleNames() {
  /* Parses samples/files/channel combinations pasted in textbox */
  let ixmap = {};
  let fnmap = {};
  for (let fn of Object.values($datasetFiles)) {
    fnmap[fn.name] = fn;
    }
  for (let line of trysamplenames.trim().split('\n')) {
    if (line.indexOf('\t') > -1) {
      line = line.trim().split('\t').map(x => x.trim());
    } else if (line.indexOf('    ') > -1) {
      line = line.trim().split('    ').map(x => x.trim());
    }
    let nps, ix, aid;
    line[0] in fnmap ? (aid = fnmap[line[0]], nps = line[1]) : false;
    line[1] in fnmap ? (aid = fnmap[line[1]], nps = line[0]) : false;
    if (aid) {
      prepdata.samples[aid.associd].newprojsample = nps;
      checkNewSampleLabelfree(aid.associd);
    }
  }
  editMade();
}

function resetNewSampleName(chan_or_sample) {
  chan_or_sample.newprojsample = '';
  checkIfNewSamples();
  editMade();
}

async function doSampleSave(ch_or_samfn, ix) { 
  /* Saves a new sample name to the project on backend */
  let postdata = {
    dataset_id: $dataset_id, 
    samplename: ch_or_samfn.newprojsample
  };
  let url = '/datasets/save/projsample/';
  let response;
  try {
    response = await postJSON(url, postdata);
  } catch(error) {
    if (error.message === '404') {
      preperrors = [preperrors, 'Save dataset before saving new samples'];
    }
    return;
  }
  // just add the latest projsample, do not just assign the whole projsamples dict, async problems!
  projsamples[response.psid] = {name: response.psname, id: response.psid};
  return [response.psid, ix];
}

async function saveNewSamples() {
  /* Goes through each of the new sample names and */
  let saves = [];
  Object.entries(prepdata.samples).filter(x => x[1].newprojsample).forEach(function(samfn) {
    saves.push(doSampleSave(samfn[1], samfn[0]));
  });
  for (let item of saves) {
    let [psid, associd] = await item;
    prepdata.samples[associd].newprojsample = '';
    prepdata.samples[associd].model = psid;
  }
  checkIfNewSamples();
}

export function validate() {
  let comperrors = [];
	for (let fn of Object.values($datasetFiles)) {
		if (!prepdata.samples[fn.associd].model && !prepdata.samples[fn.associd].newprojsample) {
			comperrors.push('Labelfree requires sample name for each file');
			break;
		}
	}	
  for (let param of Object.values(prepdata.params).filter(p => p.inputtype !== 'checkbox')) {
    if (param.model === undefined || param.model === '') {
			comperrors.push(param.title + ' is required');
		}
	}
  for (let param of Object.values(prepdata.params).filter(p => p.inputtype === 'checkbox')) {
    if (!param.fields.some(f => f.checked)) {
			comperrors.push(param.title + ' is required');
		}
	}
	if (!Object.keys(prepdata.species).length) {
		comperrors.push('Organism(s) is/are required');
	}
  return comperrors;
}

export async function save() {
  errors = validate();
  if (!Object.keys($datasetFiles).length) {
    preperrors = [...preperrors, 'Add files before saving data'];
  }
  if (!$dataset_id) {
    // FIXME Is this possible?
    preperrors = [...preperrors, 'Save dataset before saving sample prep'];
  }
  if (errors.length === 0 && preperrors.length === 0) { 
    let postdata = {
      dataset_id: $dataset_id,
      params: prepdata.params,
      species: prepdata.species,
    };
    postdata.filenames = Object.values($datasetFiles);
    postdata.samples = prepdata.samples;
    let url = '/datasets/save/seqsamples/';
    await postJSON(url, postdata);
    fetchData();
  }
}

async function fetchData() {
  let url = '/datasets/show/seqsamples/';
  url = $dataset_id ? url + $dataset_id : url;
	const response = await getJSON(url);
  for (let [key, val] of Object.entries(response)) { prepdata[key] = val; }
  edited = false;
}

onMount(async() => {
  await fetchData();
})

</script>


<h5 id="sampleprep" class="has-text-primary title is-5">
  {#if stored}
  <i class="icon fas fa-check-circle"></i>
  {:else if edited}
  <i class="icon fas fa-edit"></i>
  {/if}
  Sample prep
  <button class="button is-small is-danger has-text-weight-bold" disabled={!edited} on:click={save}>Save</button>
  <button class="button is-small is-info has-text-weight-bold" disabled={!edited} on:click={fetchData}>Revert</button>
</h5>

<ErrorNotif errors={preperrors} />

<div class="field">
  <label class="label">Organism</label>
  <DynamicSelect intext="Type to get more organisms" fixedoptions={prepdata.allspecies} fixedorder={Object.values(prepdata.allspecies).sort((a,b) => b.total - a.total).map(x => x.id)} bind:selectval={selectedspecies} fetchUrl="/datasets/show/species/" bind:fetchedData={fetchedSpecies} niceName={niceSpecies} on:selectedvalue={addOrganism} />
</div>
<div class="tags">
  {#each prepdata.species as spec}
  <span class="tag is-medium is-info">
    {niceSpecies(spec)}
    <button class="delete is-small" on:click={e => removeOrganism(spec.id)}></button>
  </span>
{/each}
</div>

{#each Object.entries(prepdata.params) as [param_id, param]}
<Param bind:param={param} on:edited={editMade} />
{/each}


<div class="field">
  <label class="label">Samples</label>
  <textarea class="textarea" bind:value={trysamplenames} placeholder="Paste your sample names here (one line per sample, tab separated sample/file or channel)"></textarea>
  <a class="button is-primary" on:click={parseSampleNames}>Parse sample names</a>
</div>
<table class="table is-fullwidth" >
  <thead>
    <tr>
      <th>Filename</th>
      <th colspan="2">Sample name 
        {#if foundNewSamples}
        <a class="button is-danger is-small is-pulled-right" on:click={saveNewSamples}>Save new samples</a>
        {:else}
        <a class="button is-danger is-small is-pulled-right" disabled>Save new samples</a>
        {/if}
      </th>
    </tr>
  </thead>
  <tbody>
    {#each Object.values($datasetFiles) as file}
    {#if file.associd in prepdata.samples }
    <tr>
      <td>{file.name}</td>
      <td>
        <div class="select">
          <select bind:value={prepdata.samples[file.associd].model} on:change={e => resetNewSampleName(prepdata.samples[file.associd])}> 
            <option disabled value="">Pick a project-sample</option>
            {#each Object.entries(projsamples) as [s_id, sample]}
            <option value={s_id}>{sample.name}</option>
            {/each}
          </select>
        </div>
      </td>
      <td><input bind:value={prepdata.samples[file.associd].newprojsample} on:change={e => checkNewSampleLabelfree(file.associd)} placeholder="or define a new sample" class="input is-normal"></td> 
    </tr>
    {/if}
    {/each}
  </tbody>
</table>
