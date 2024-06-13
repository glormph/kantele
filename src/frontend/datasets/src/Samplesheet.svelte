<script>
import { onMount } from 'svelte';
import { getJSON, postJSON } from './funcJSON.js'
import Param from './Param.svelte';
import ErrorNotif from './ErrorNotif.svelte';
import DynamicSelect from './DynamicSelect.svelte';
import { dataset_id, datasetFiles, projsamples } from './stores.js';

export let errors;

let preperrors = [];
let edited = true;
let fetchedSpecies = {};
let saved = false;

$: stored = $dataset_id && !edited && saved;


function editMade() { 
  errors = errors.length ? validate() : [];
  edited = true; 
}

let allspecies = false;
let allsampletypes = false;

let prepdata = {
  //params: [],
  lf_qtid: false,
  species: [],
  samples: {},
  quants: {},
  labeled: false,
  sampletypes: [],
}

let sampletype;
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

function removeOrganismMultiplex(chix, org_id) {
  // Would like to pass channel but then the tags dont update, so pass ch index chix instead
  prepdata.quants[prepdata.labeled].chans[chix].species = prepdata.quants[prepdata.labeled].chans[chix].species.filter(x => x.id !== org_id);
  prepdata.quants[prepdata.labeled].chans[chix].model = false;
  editMade();
}

function addOrganismMultiplex(channel) {
  const selected = channel.selectedspecies;
  const species = (selected in allspecies) ? allspecies[selected] : fetchedSpecies[selected];
  channel.species = [...channel.species, species];
  channel.model = false;
  editMade();
}

function copyOrganismsMultiplexDown(chix) {
  let fromch = false
  const tocopy = prepdata.quants[prepdata.labeled].chans[chix].species;
  for (let [ix, channel] of prepdata.quants[prepdata.labeled].chans.entries()) {
    prepdata.quants[prepdata.labeled].chans[ix].model = false;
    if (fromch || ix === chix) {
      prepdata.quants[prepdata.labeled].chans[ix].species = tocopy;
      fromch = true
    }
  }
  editMade();
}

function removeOrganismFileSample(fn_id, org_id) {
  prepdata.samples[fn_id].species = prepdata.samples[fn_id].species.filter(x => x.id !== org_id);
  prepdata.samples[fn_id].model = false;
  editMade();
}

function addOrganismFileSample(fn_id) {
  const selected = prepdata.samples[fn_id].selectedspecies;
  const species = (selected in allspecies) ? allspecies[selected] : fetchedSpecies[selected];
  prepdata.samples[fn_id].species = [...prepdata.samples[fn_id].species, species];
  prepdata.samples[fn_id].model = false;
  editMade();
}

function copyOrganismsFilesDown(fn_id) {
  let fromfn = false
  const tocopy = prepdata.samples[fn_id].species;
  for (const fn of Object.values($datasetFiles)) {
    prepdata.samples[fn.associd].model = false;
    if (fromfn || fn.associd === fn_id) {
      prepdata.samples[fn.associd].species = tocopy;
      fromfn = true
    }
  }
  editMade();
}


function removeSampletypeFileSample(fn_id, stype_id) {
  prepdata.samples[fn_id].sampletypes = prepdata.samples[fn_id].sampletypes.filter(x => x.id !== stype_id);
  prepdata.samples[fn_id].model = false;
  editMade();
}

function addSampletypeFileSample(fn_id) {
  const stype = allsampletypes[prepdata.samples[fn_id].selectedsampletype];
  prepdata.samples[fn_id].sampletypes = [...prepdata.samples[fn_id].sampletypes, stype];
  prepdata.samples[fn_id].model = false;
  editMade();
}

function copySampletypesFilesDown(fn_id) {
  let fromfn = false
  const tocopy = prepdata.samples[fn_id].sampletypes;
  for (const fn of Object.values($datasetFiles)) {
    prepdata.samples[fn.associd].model = false;
    if (fromfn || fn.associd === fn_id) {
      prepdata.samples[fn.associd].sampletypes = tocopy;
      fromfn = true
    }
  }
  editMade();
}

function removeSampletypeMultiplex(chix, stype_id) {
  prepdata.quants[prepdata.labeled].chans[chix].sampletypes = prepdata.quants[prepdata.labeled].chans[chix].sampletypes.filter(x => x.id !== stype_id);
  prepdata.quants[prepdata.labeled].chans[chix].model = false;
  editMade();
}

function addSampletypeMultiplex(channel) {
  const stype = allsampletypes[channel.selectedsampletype];
  channel.sampletypes = [...channel.sampletypes, stype];
  channel.model = false;
  editMade();
}

function copySampletypesMultiplexDown(chix) {
  let fromch = false
  const tocopy = prepdata.quants[prepdata.labeled].chans[chix].sampletypes;
  for (let [ix, channel] of prepdata.quants[prepdata.labeled].chans.entries()) {
    prepdata.quants[prepdata.labeled].chans[ix].model = false;
    if (fromch || ix === chix) {
      prepdata.quants[prepdata.labeled].chans[ix].sampletypes = tocopy;
      fromch = true;
    }
  }
  editMade();
}


function changeSampleNameChannel(chix) {
  prepdata.quants[prepdata.labeled].chans[chix].model = '';
  prepdata.quants[prepdata.labeled].chans[chix].projsam_dup_use = false;
  prepdata.quants[prepdata.labeled].chans[chix].projsam_dup = false;
  prepdata.quants[prepdata.labeled].chans[chix].species_error = [];
  prepdata.quants[prepdata.labeled].chans[chix].sampletypes_error = [];
  editMade();
}


function changeSampleNameFile(fn_id) {
  prepdata.samples[fn_id].model = '';
  prepdata.samples[fn_id].projsam_dup = false;
  prepdata.samples[fn_id].projsam_dup_use = false;
  prepdata.samples[fn_id].species_error = [];
  prepdata.samples[fn_id].sampletypes_error = [];
  editMade();
}


function useDuplicateFileSam(fn_id) {
  prepdata.samples[fn_id].model = prepdata.samples[fn_id].projsam_dup;
  prepdata.samples[fn_id].projsam_dup_use = prepdata.samples[fn_id].projsam_dup;
  prepdata.samples[fn_id].projsam_dup = false;
}


function useDuplicateAllFileSam() {
  Object.entries(prepdata.samples).forEach(([fn_id, sample]) => {
    if (!sample.projsam_dup_use) {
      useDuplicateFileSam(fn_id);
    }
  });
}

function useDuplicateSampleChannel(chix) {
  prepdata.quants[prepdata.labeled].chans[chix].model = prepdata.quants[prepdata.labeled].chans[chix].projsam_dup;
  prepdata.quants[prepdata.labeled].chans[chix].projsam_dup_use = prepdata.quants[prepdata.labeled].chans[chix].projsam_dup;
  prepdata.quants[prepdata.labeled].chans[chix].projsam_dup = false;
}

function useDuplicateSampleAllChannel() {
  prepdata.quants[prepdata.labeled].chans.forEach((channel, chix) => {
    if (!channel.projsam_dup_use) {
      useDuplicateSampleChannel(chix);
    }
  });
}


function checkSamplesIfNewFiles() {
  /* create new sample fields for added files, if files are added in frontend
  and page isnt updated */
  const assocs = Object.values($datasetFiles).map(x => x.associd);
  prepdata.samples = Object.fromEntries(Object.entries(prepdata.samples).filter(x => assocs.indexOf(Number(x[0])) > -1));
  for (let associd of assocs.filter(x => !(x in prepdata.samples))) {
    // FIXME need more here!
    prepdata.samples[associd] = {model: '', samplename: '', selectedspecies: '', species: '',
      selectedsampletype: '', sampletypes: [], projsam_dup: false, projsam_dup_use: false,
      sampletypes_error: [], species_error: []};
  }
}

$: $datasetFiles ? checkSamplesIfNewFiles() : '';



function parseSampleNames() {
  /* Parses samples/files/channel combinations pasted in textbox */
  let ixmap = {};
  let fnmap = {};
  if (prepdata.labeled) {
    prepdata.quants[prepdata.labeled].chans.forEach(function(ch, ix) {
      ixmap[ch.name] = ix;
    });
  } else {
    for (let fn of Object.values($datasetFiles)) {
      fnmap[fn.name] = fn;
    }
  }
  for (let line of trysamplenames.trim().split('\n')) {
    if (line.indexOf('\t') > -1) {
      line = line.trim().split('\t').map(x => x.trim());
    } else if (line.indexOf('    ') > -1) {
      line = line.trim().split('    ').map(x => x.trim());
    }
    let nps, ix, aid;
    if (prepdata.labeled) {
      line[0] in ixmap ? (ix = ixmap[line[0]], nps = line[1]) : false;
      line[1] in ixmap ? (ix = ixmap[line[1]], nps = line[0]) : false;
      if (ix > -1) {
        prepdata.quants[prepdata.labeled].chans[ix].samplename = nps;
      }
    } else {
      line[0] in fnmap ? (aid = fnmap[line[0]], nps = line[1]) : false;
      line[1] in fnmap ? (aid = fnmap[line[1]], nps = line[0]) : false;
      if (aid) {
        prepdata.samples[aid.associd].samplename = nps;
      }
    }
  }
  editMade();
}


export function validate() {
  let comperrors = [];
  if (!prepdata.labeled) {
		for (let fn of Object.values($datasetFiles)) {
			if (!prepdata.samples[fn.associd].model && !prepdata.samples[fn.associd].samplename) {
				comperrors.push('A sample name for each file is required');
				break;
			}
		}	
  } else {
		for (let ch of prepdata.quants[prepdata.labeled].chans) {
			if (ch.model === '' && !ch.samplename) { 
				comperrors.push('Sample name for each channel is required');
				break;
			}
		}
	}
//  for (let param of Object.values(prepdata.params).filter(p => p.inputtype !== 'checkbox')) {
//    if (param.model === undefined || param.model === '') {
//			comperrors.push(param.title + ' is required');
//		}
//	}
//  for (let param of Object.values(prepdata.params).filter(p => p.inputtype === 'checkbox')) {
//    if (!param.fields.some(f => f.checked)) {
//			comperrors.push(param.title + ' is required');
//		}
//	}
  return comperrors;
}

// FIXME - when changing sample name, it needs to remove the errors also!

export async function save() {
  errors = validate();
  preperrors = [];
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
      samples: prepdata.samples,
      multiplex: false,
      qtype: prepdata.labeled ? prepdata.labeled : prepdata.lf_qtid,
    };
    if (prepdata.labeled) {
      postdata.multiplex = prepdata.quants[prepdata.labeled];
    }
    let url = '/datasets/save/samples/';
    const resp = await postJSON(url, postdata);

    if (!resp.ok && 'sample_dups' in resp) {
      preperrors = [...preperrors, resp.error];
      if (prepdata.labeled) {
        const id_to_ix = Object.fromEntries(prepdata.quants[prepdata.labeled].chans
          .map((ch, ix) => [ch.id, ix]));
        Object.entries(resp.sample_dups).forEach(([chid, projsam]) => {
          const chix = id_to_ix[chid];
          prepdata.quants[prepdata.labeled].chans[chix].projsam_dup = projsam.id;
          prepdata.quants[prepdata.labeled].chans[chix].duprun = projsam.duprun_example;
          prepdata.quants[prepdata.labeled].chans[chix].sampletypes_error = projsam.sampletypes_error;
          prepdata.quants[prepdata.labeled].chans[chix].species_error = projsam.species_error;
        });
      } else {
        Object.entries(resp.sample_dups).forEach(([fid, projsam]) => {
          prepdata.samples[fid].projsam_dup = projsam.id;
          prepdata.samples[fid].duprun = projsam.duprun_example;
          prepdata.samples[fid].sampletypes_error = projsam.sampletypes_error;
          prepdata.samples[fid].species_error = projsam.species_error;
        });
      }
    } else if (!resp.ok && resp.error) {
      preperrors = [...preperrors, resp.error];

    } else {
    fetchData();
    }
  }
}

async function fetchData() {
  let url = '/datasets/show/samples/';
  url = $dataset_id ? url + $dataset_id : url;
	const response = await getJSON(url);
  for (let [key, val] of Object.entries(response)) {
    if (key in prepdata) {
      prepdata[key] = val;
    }
  }
  allspecies = response.allspecies;
  allsampletypes = response.allsampletypes;
  if (Object.keys(prepdata.samples).length) {
    saved = true;
  }
  edited = false;
}

onMount(async() => {
  await fetchData();
})

</script>


<h5 id="sampleprep" class="has-text-primary title is-5">
  {#if stored}
  <i class="icon fas fa-check-circle"></i>
  {:else}
  <i class="icon fas fa-edit"></i>
  {/if}
  Sample sheet
  <button class="button is-small is-danger has-text-weight-bold" disabled={!edited} on:click={save}>Save</button>
  <button class="button is-small is-info has-text-weight-bold" disabled={!edited} on:click={fetchData}>Revert</button>
</h5>

<ErrorNotif errors={preperrors} />


<div class="field">
  <label class="label">Are samples labeled multiplex?</label>
  <div class="control">
    <div class="select">
      <select bind:value={prepdata.labeled}>
        <option value={false}>No</option>
        {#each Object.values(prepdata.quants) as quant}
        <option value={quant.id}>{quant.name}</option>
        {/each}
      </select>
    </div>
  </div>
</div>


<div class="field">
  <label class="label">Samples</label>
  <textarea class="textarea" bind:value={trysamplenames} placeholder="Paste your sample names here (one line per sample, tab (or 4 spaces) separated sample/file or channel)"></textarea>
  <a class="button is-primary" on:click={parseSampleNames}>Parse sample names</a>
</div>

<table class="table is-fullwidth" >
  <thead>
    <tr>
      {#if prepdata.labeled}
      <th>Channel</th>
      {:else}
      <th>Filename</th>
      {/if}
      <th>Sample name</th>
      <th>Organism</th>
      <th>Type</th>
    </tr>
  </thead>
  <tbody>
    {#if prepdata.labeled}
    {#each prepdata.quants[prepdata.labeled].chans as channel, chix}
    <tr>
      <!-- FIXME empty channel -->
      <td>{channel.name}</td>
      <td>
        <input bind:value={channel.samplename} on:change={e => changeSampleNameChannel(chix)} class={channel.projsam_dup ? "input is-danger": "input is-normal"}>
        {#if channel.projsam_dup}
        <p class="help is-danger">This sample ID exists in the database for this project,<br>
        you cannot change an existing sample's types or organisms in this sheet,<br>
        please either use a different sample ID or confirm it is the same sample as used in:</p>
        <p class="help is-info">{channel.duprun}</p>
        <p>
        <button class="button is-small" on:click={e => useDuplicateSampleChannel(chix)}>Accept</button>
        <button class="button is-small" on:click={useDuplicateSampleAllChannel}>Accept all</button>
        </p>
        {:else if channel.projsam_dup_use}
        <p class="help is-success">
        Using sample {channel.projsam_dup_use}
        </p>
        {/if}
      </td>
      <td> 
        <DynamicSelect placeholder="Type to get more organisms" fixedoptions={allspecies} fixedorder={Object.values(allspecies).sort((a,b) => b.total - a.total).map(x => x.id)} bind:selectval={channel.selectedspecies} fetchUrl="/datasets/show/species/" bind:fetchedData={fetchedSpecies} niceName={niceSpecies} on:selectedvalue={e => addOrganismMultiplex(channel)} />
        <div class="tags">
          <button class="button is-white icon" on:click={e => copyOrganismsMultiplexDown(chix)} aria-label="Apply values to all fields below"><i class="fas fa-sort-amount-down"></i></button>
          {#each prepdata.quants[prepdata.labeled].chans[chix].species as spec}
          <span class="tag is-medium is-info">
            {niceSpecies(spec)}
            <button class="delete is-small" on:click={e => removeOrganismMultiplex(chix, spec.id)}></button>
          </span>
          {/each}
        </div>

        <div class="field is-grouped is-grouped-multiline">
          {#each prepdata.quants[prepdata.labeled].chans[chix].species_error as spec}
          <!-- FIXME this for removed/new tags -->
          <div class="control">
            <div class="tags has-addons">
              <span class="tag is-info"> {niceSpecies(spec)} </span>
              {#if spec.remove}
              <span class="tag is-danger">Not in duplicate sample</span>
              {:else if spec.add}
              <span class="tag is-success">In duplicate sample</span>
              {/if}
            </div>
          </div>
          {/each}
        </div>
      </td>

      <td> 
        <DynamicSelect fixedoptions={allsampletypes} bind:selectval={channel.selectedsampletype} niceName={x => x.name} on:selectedvalue={e => addSampletypeMultiplex(channel)} />
        <button class="button is-white icon" on:click={e => copySampletypesMultiplexDown(chix)} aria-label="Apply values to all fields below"><i class="fas fa-sort-amount-down"></i></button>
        <!-- FIXME button accept duplicate -->
        <div class="tags">
          {#each prepdata.quants[prepdata.labeled].chans[chix].sampletypes as stype}
          <span class="tag is-medium is-info">
            {stype.name}
            <button class="delete is-small" on:click={e => removeSampletypeMultiplex(chix, stype.id)}></button>
          </span>
          {/each}
        </div>

        <div class="field is-grouped is-grouped-multiline">
          {#each prepdata.quants[prepdata.labeled].chans[chix].sampletypes_error as stype}
          <!-- FIXME this for removed/new tags -->
          <div class="control">
            <div class="tags has-addons">
              <span class="tag is-info"> {stype.name} </span>
              {#if stype.remove}
              <span class="tag is-danger">Not in duplicate sample</span>
              {:else if stype.add}
              <span class="tag is-success">In duplicate sample</span>
              {/if}
            </div>
          </div>
          {/each}
        </div>
      </td>
    </tr>
    {/each}

    {:else if allspecies}
    {#each Object.values($datasetFiles) as file}
    {#if file.associd in prepdata.samples}
    <tr>
      <td>{file.name}</td>
      <td>
        <input bind:value={prepdata.samples[file.associd].samplename} on:change={e => changeSampleNameFile(file.associd)} class={prepdata.samples[file.associd].projsam_dup ? "input is-danger" : "input is-normal"}>
        {#if prepdata.samples[file.associd].projsam_dup}
        <p class="help is-danger">This sample ID exists in the database for this project,<br>
        you cannot change an existing sample's types or organisms in this sheet,<br>
        please either use a different sample ID or confirm it is the same sample as used in:</p>
        <p class="help is-info">{prepdata.samples[file.associd].duprun}</p>
        <p>
        <button class="button is-small" on:click={e => useDuplicateFileSam(file.associd)}>Accept</button>
        <button class="button is-small" on:click={useDuplicateAllFileSam}>Accept all</button>
        </p>
        {:else if prepdata.samples[file.associd].projsam_dup_use}
        <p class="help is-success">
        Using sample {prepdata.samples[file.associd].projsam_dup_use}
        </p>
        {/if}
      </td>
      <td>
        <DynamicSelect placeholder="Type to get more organisms" fixedoptions={allspecies} fixedorder={Object.values(allspecies).sort((a,b) => b.total - a.total).map(x => x.id)} bind:selectval={prepdata.samples[file.associd].selectedspecies} fetchUrl="/datasets/show/species/" bind:fetchedData={fetchedSpecies} niceName={niceSpecies} on:selectedvalue={e => addOrganismFileSample(file.associd)} />
        <div class="tags">
          <button class="button is-white icon" on:click={e => copyOrganismsFilesDown(file.associd)} aria-label="Apply values to all fields below"><i class="fas fa-sort-amount-down"></i></button>
          {#each prepdata.samples[file.associd].species as spec}
          <span class="tag is-medium is-info">
            {niceSpecies(spec)}
            <button class="delete is-small" on:click={e => removeOrganismFileSample(file.associd, spec.id)}></button>
          </span>
          {/each}
        </div>

        <div class="field is-grouped is-grouped-multiline">
          {#each prepdata.samples[file.associd].species_error as spec}
          <!-- FIXME this for removed/new tags -->
          <div class="control">
            <div class="tags has-addons">
              <span class="tag is-info"> {niceSpecies(spec)} </span>
              {#if spec.remove}
              <span class="tag is-danger">Not in duplicate sample</span>
              {:else if spec.add}
              <span class="tag is-success">In duplicate sample</span>
              {/if}
            </div>
          </div>
          {/each}
        </div>
      </td>
      <td>
        <DynamicSelect fixedoptions={allsampletypes} bind:selectval={prepdata.samples[file.associd].selectedsampletype} niceName={x => x.name} on:selectedvalue={e => addSampletypeFileSample(file.associd)} />
        <div class="tags">
          <button class="button is-white icon" on:click={e => copySampletypesFilesDown(file.associd)} aria-label="Apply values to all fields below"><i class="fas fa-sort-amount-down"></i></button>
          {#each prepdata.samples[file.associd].sampletypes as stype}
          <span class="tag is-medium is-info">
            {stype.name}
            <button class="delete is-small" on:click={e => removeSampletypeFileSample(file.associd, stype.id)}></button>
          </span>
          {/each}
        </div>

        <div class="field is-grouped is-grouped-multiline">
          {#each prepdata.samples[file.associd].sampletypes_error as stype}
          <!-- FIXME this for removed/new tags -->
          <div class="control">
            <div class="tags has-addons">
              <span class="tag is-info"> {stype.name} </span>
              {#if stype.remove}
              <span class="tag is-danger">Not in duplicate sample</span>
              {:else if stype.add}
              <span class="tag is-success">In duplicate sample</span>
              {/if}
            </div>
          </div>
          {/each}
        </div>
      </td>

    </tr>
    {/if}
    {/each}
    {/if}
  </tbody>
</table>

<button class="button is-small is-danger has-text-weight-bold" disabled={!edited} on:click={save}>Save</button>
<button class="button is-small is-info has-text-weight-bold" disabled={!edited} on:click={fetchData}>Revert</button>
