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

$: stored = $dataset_id && !edited;


function editMade() { 
  errors = errors.length ? validate() : [];
  edited = true; 
}

let prepdata = {
  params: [],
  enzymes: [],
  no_enzyme: false,
  quanttype: '',
  quants: {},
  labelfree_multisample: true,
  labelfree_singlesample: {},
  allspecies: [],
  species: [],
  samples: {},
}

let selectedspecies;
let trysamplenames = '';
let labelfree_quant_id;
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

async function fetchSpecies(intext) {
  if (intext.length > 2) {
    return await getJSON(`/datasets/show/species/?q=${intext}`);
  }
}

function removeOrganism(org_id) {
  prepdata.species = prepdata.species.filter(x => x.id !== org_id);
  editMade();
}

function addOrganism() {
  prepdata.species = [...prepdata.species, prepdata.allspecies[selectedspecies]];
  editMade();
}

$: isLabelfree = prepdata.quanttype === labelfree_quant_id;

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
  if (prepdata.quanttype !== labelfree_quant_id) { // Cannot check isLabelfree here, that is slower to update than the call to this func
    foundNewSamples = prepdata.quants[prepdata.quanttype].chans.some(ch => ch.newprojsample !== '');
  } else if (!prepdata.labelfree_multisample) {
    foundNewSamples = prepdata.labelfree_singlesample.newprojsample !== '';
  } else {
    foundNewSamples = Object.values(prepdata.samples).some(x => x.newprojsample !== '')
  }
}

function checkNewSampleLabelfree(associd=false) {
  /* Checks if entered sample is found in project or if it is a new sample */
  let sample;
  if (!prepdata.labelfree_multisample) {
    sample = prepdata.labelfree_singlesample.newprojsample
  } else {
    sample = prepdata.samples[associd].newprojsample;
  }
  if (sample == '') { 
    return 
  } else {
    let uppername = sample.trim().toUpperCase();
    let found = Object.entries(projsamples).filter(x=>x[1].name.toUpperCase() == uppername).map(x=>x[0])[0]
    if (found && !prepdata.labelfree_multisample) {
      prepdata.labelfree_singlesample.model = found;
      prepdata.labelfree_singlesample.newprojsample = '';
    } else if (found) {
      prepdata.samples[associd].model = found;
      prepdata.samples[associd].newprojsample = '';
      /* new samples filled in will reset the dropdown ones, do not do this, only on save */
//    }  else if (prepdata.labelfree_multisample) {
//      prepdata.samples[associd].model = '';
//    } else {
//      prepdata.labelfree_singlesample.model = '';
    }
    checkIfNewSamples();
  }
}

function checkNewSampleIso(chanix) {
  /* Checks if entered sample is found in project or if it is a new sample */
  if (prepdata.quants[prepdata.quanttype].chans[chanix].newprojsample == '') { 
    /* at fetchdata, samples are assigned, on:change fires and this is called */
    return 
  } else {
    let uppername = prepdata.quants[prepdata.quanttype].chans[chanix].newprojsample.trim().toUpperCase();
    let found = Object.entries(projsamples).filter(x=>x[1].name.toUpperCase() == uppername).map(x=>x[0])[0]
    if (found) {
      prepdata.quants[prepdata.quanttype].chans[chanix].model = found;
      prepdata.quants[prepdata.quanttype].chans[chanix].newprojsample = '';
    }
    checkIfNewSamples();
  }
}

function parseSampleNames() {
  /* Parses samples/files/channel combinations pasted in textbox */
  let ixmap = {};
  let fnmap = {};
  if (isLabelfree && !prepdata.labelfree_multisample) {
    return 0;
  } else if (isLabelfree) {
    for (let fn of Object.values($datasetFiles)) {
      fnmap[fn.name] = fn;
    }
  } else {
    prepdata.quants[prepdata.quanttype].chans.forEach(function(ch, ix) {
      ixmap[ch.name] = ix;
    });
    }
  for (let line of trysamplenames.trim().split('\n')) {
    if (line.indexOf('\t') > -1) {
      line = line.trim().split('\t').map(x => x.trim());
    } else if (line.indexOf('    ') > -1) {
      line = line.trim().split('    ').map(x => x.trim());
    }
    let nps, ix, aid;
    if (isLabelfree) {
      line[0] in fnmap ? (aid = fnmap[line[0]], nps = line[1]) : false;
      line[1] in fnmap ? (aid = fnmap[line[1]], nps = line[0]) : false;
      if (aid) {
        prepdata.samples[aid.associd].newprojsample = nps;
        checkNewSampleLabelfree(aid.associd);
      }
    } else {
      line[0] in ixmap ? (ix = ixmap[line[0]], nps = line[1]) : false;
      line[1] in ixmap ? (ix = ixmap[line[1]], nps = line[0]) : false;
      if (ix > -1) {
        prepdata.quants[prepdata.quanttype].chans[ix].newprojsample = nps;
        checkNewSampleIso(ix);
      }
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
  if (!isLabelfree) {
    prepdata.quants[prepdata.quanttype].chans.map(function(ch, ix) { return [ix, ch]}).filter(ch => ch[1].newprojsample).forEach(function(ch) {
      saves.push(doSampleSave(ch[1], ch[0]));
    }); 
    for (let item of saves) {
      let [psid, ix] = await item;
      prepdata.quants[prepdata.quanttype].chans[ix].newprojsample = '';
      prepdata.quants[prepdata.quanttype].chans[ix].model = psid;
    }
  } else if (!prepdata.labelfree_multisample && foundNewSamples) {
    const savedsample = await doSampleSave(prepdata.labelfree_singlesample);
    prepdata.labelfree_singlesample.model = savedsample[0];
    prepdata.labelfree_singlesample.newprojsample = '';
  } else {
    Object.entries(prepdata.samples).filter(x => x[1].newprojsample).forEach(function(samfn) {
      saves.push(doSampleSave(samfn[1], samfn[0]));
    });
    for (let item of saves) {
      let [psid, associd] = await item;
      prepdata.samples[associd].newprojsample = '';
      prepdata.samples[associd].model = psid;
    }
  }
  checkIfNewSamples();
}

export function validate() {
  let comperrors = [];
	if (!prepdata.no_enzyme && !prepdata.enzymes.filter.length) {
		comperrors.push('Enzyme selection is required');
	}
	if (!prepdata.quanttype) {
		comperrors.push('Quant type selection is required');
	}
  if (isLabelfree && prepdata.labelfree_multisample) {
		for (let fn of Object.values($datasetFiles)) {
			if (!prepdata.samples[fn.associd].model && !prepdata.samples[fn.associd].newprojsample) {
				comperrors.push('Labelfree requires sample name for each file');
				break;
			}
		}	
  } else if (isLabelfree) {
    if (prepdata.labelfree_singlesample.model === '') {
      comperrors.push('Labelfree singlesample requires a sample name');
    }
	} else if (prepdata.quanttype in prepdata.quants) {
		for (let ch of prepdata.quants[prepdata.quanttype].chans) {
			if (ch.model === '') { 
				comperrors.push('Sample name for each channel is required');
				break;
			}
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
  if (!Object.keys($datasetFiles).length && isLabelfree) {
    preperrors = [...preperrors, 'Add files before saving data'];
  }
  if (!$dataset_id) {
    preperrors = [...preperrors, 'Save dataset before saving sample prep'];
  }
  if (errors.length === 0 && preperrors.length === 0) { 
    let postdata = {
      dataset_id: $dataset_id,
      enzymes: prepdata.no_enzyme ? [] : prepdata.enzymes,
      params: prepdata.params,
      quanttype: prepdata.quanttype,
      labelfree: isLabelfree,
      species: prepdata.species,
    };
    if (!isLabelfree) {
      postdata.samples = prepdata.quants[prepdata.quanttype].chans;
    } else if (prepdata.labelfree_multisample) {
      postdata.filenames = Object.values($datasetFiles);
      postdata.samples = prepdata.samples;
    } else {
      postdata.filenames = Object.values($datasetFiles);
      postdata.samples = Object.fromEntries(postdata.filenames.map(fn => [fn.associd, prepdata.labelfree_singlesample]));
    }
    let url = '/datasets/save/sampleprep/';
    await postJSON(url, postdata);
    fetchData();
  }
}

async function fetchData() {
  let url = '/datasets/show/sampleprep/';
  url = $dataset_id ? url + $dataset_id : url;
	const response = await getJSON(url);
  for (let [key, val] of Object.entries(response)) { prepdata[key] = val; }
  labelfree_quant_id = Object.entries(prepdata.quants).filter(x => x[1].name === 'labelfree').map(x=>Number(x[0])).pop();
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
  <DynamicSelect intext="Type to get more organisms" bind:options={prepdata.allspecies} optorder={Object.values(prepdata.allspecies).sort((a,b) => b.total - a.total).map(x => x.id)} bind:selectval={selectedspecies} fetchUrl="/datasets/show/species/" niceName={niceSpecies} on:selectedvalue={addOrganism} />
</div>
<div class="tags">
  {#each prepdata.species as spec}
  <span class="tag is-medium is-info">
    {niceSpecies(spec)}
    <button class="delete is-small" on:click={e => removeOrganism(spec.id)}></button>
  </span>
{/each}
</div>

<div class="field">
  <label class="label">Enzymes</label>
  <input type="checkbox" on:change={editMade} bind:checked={prepdata.no_enzyme}>No enzyme
  {#if !prepdata.no_enzyme}
  {#each prepdata.enzymes as enzyme}
  <div class="control">
    <input on:change={editMade} bind:checked={enzyme.checked} type="checkbox">{enzyme.name}
  </div>
  {/each}
  {/if}
</div>

{#each Object.entries(prepdata.params) as [param_id, param]}
<Param bind:param={param} on:edited={editMade} />
{/each}


<div class="field">
  <label class="label">Quant type</label>
  <div class="control">
    <div class="select">
      <select on:change={checkIfNewSamples} bind:value={prepdata.quanttype}>
        <option disabled value="">Please select one</option>
        {#each Object.values(prepdata.quants) as quant}
        <option value={quant.id}>{quant.name}</option>
        {/each}
      </select>
    </div>
  </div>
</div>

{#if prepdata.quanttype}
<div class="field">
  <label class="label">Samples</label>
  <textarea class="textarea" bind:value={trysamplenames} placeholder="Try this: paste your sample names here (one line per sample, tab separated sample/file or channel)"></textarea>
  <a class="button is-primary" on:click={parseSampleNames}>Parse sample names</a>
  <div class="control">
    {#if isLabelfree}
    <div id="labelfree_samples">
      <input type="checkbox" on:change={checkIfNewSamples} bind:checked={prepdata.labelfree_multisample}>One sample per file?
    </div>
    {/if}
  </div>
</div>
<table class="table is-fullwidth" >
  <thead>
    <tr>
      {#if isLabelfree && prepdata.labelfree_multisample}
      <th>Filename</th>
      {:else if !isLabelfree}
      <th>Channel</th>
      {/if} 
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
    {#if !isLabelfree}
    {#each prepdata.quants[prepdata.quanttype].chans as channel, chix}
    <tr>
      <td>{channel.name}</td>
      <td>
        <div class="select">
          <select bind:value={channel.model} on:change={e => resetNewSampleName(channel)}>
            <option disabled value="">Pick a project-sample</option>
            {#each Object.entries(projsamples) as [s_id, sample]}
            <option value={s_id}>{sample.name}</option>
            {/each}
          </select>
        </div>
      </td>
      <td>
        <p class={channel.newprojsample && foundNewSamples ? 'control has-icons-left' : 'control'}>
        <input bind:value={channel.newprojsample} class="input is-normal" on:change={e => checkNewSampleIso(chix)} placeholder="or define a new sample">
        {#if foundNewSamples && channel.newprojsample}
        <span class="icon is-left has-text-danger">
          <i class="fas fa-asterisk"></i>
        </span>
        {/if}
        </p>
      </td>
    </tr>
    {/each}
    {:else if isLabelfree && prepdata.labelfree_multisample}
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
    {:else if isLabelfree && Object.keys($datasetFiles).length}
    <tr><td>
        <div class="select">
          <select bind:value={prepdata.labelfree_singlesample.model} on:change={e => resetNewSampleName(prepdata.labelfree_singlesample)}>
            <option disabled value="">Pick a project-sample</option>
            {#each Object.entries(projsamples) as [s_id, sample]}
            <option value={s_id}>{sample.name}</option>
            {/each}
          </select>
        </div>
      </td>
      <td><input bind:value={prepdata.labelfree_singlesample.newprojsample} on:change={e => checkNewSampleLabelfree(prepdata.labelfree_singlesample)} placeholder="or define a new sample" class="input is-normal"></td>
    </tr>

    {/if}
  </tbody>
</table>
{/if}
