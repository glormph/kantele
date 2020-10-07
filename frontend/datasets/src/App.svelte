<script>
import { getJSON, postJSON } from './funcJSON.js'
import { dataset_id, datatype_id, datasetFiles, projsamples } from './stores.js';
import { onMount } from 'svelte';
import Acquicomp from './Acquicomp.svelte';
import Prepcomp from './Prepcomp.svelte';
import Msdata from './Msdata.svelte';
import LCheck from './LCheck.svelte';
import Files from './Files.svelte';
import ErrorNotif from './ErrorNotif.svelte';
  
// FIXME dataset_id is global on django template and not updated on save, change that!, FIXED???
// FIXME files do not get updated
if (init_dataset_id) { dataset_id.set(init_dataset_id) };


let mssubcomp;
let acquicomp;
let prepcomp;
let lccomp;
let filescomp;
let edited = false;
let errors = {
  basics: [],
  sprep: [],
  acqui: [],
  lc: [],
};
let saveerrors = Object.assign({}, errors);
let comperrors = [];


let dsinfo = {
  datatype_id: '',
  project_id: '',
  ptype_id: '',
  storage_location: '',
  newprojectname: '',
  experiment_id: '',
  runname: '',
  pi: '',
  externalcontactmail: '',
  prefrac_id: '',
  prefrac_length: '',
  prefrac_amount: '',
  hiriefrange: '',
}

let pdata = {
  datasettypes: [],
  ptypes: [],
  projects: [],
  local_ptype_id: '',
  external_pis: [],
  prefracs: [],
  hirief_ranges: [],
}

let components = [];
let isNewProject = false;
let isNewExperiment = false;
let isNewPI = false;
let experiments = []
let stored = true;
let tabshow = 'meta';
let tabcolor = 'has-text-grey-lighter';
  // Yes, for microscopy/genomics, we need separation between samples/prep
  // files is given, and possibly samples as well, check it out but samples is needed for:
  // - QMS, LCheck?, IP, TPP, microscopy, QC?, genomics

$: showMsdata = components.indexOf('acquisition') > -1;
$: isExternal = dsinfo.ptype_id && dsinfo.ptype_id !== pdata.local_ptype_id;

async function getcomponents() {
  const result = await getJSON(`/datasets/show/components/${dsinfo.datatype_id}`);
  components = result.components;
}

async function project_selected(event=false, saved=false) {
  if (dsinfo.project_id) {
    const result = await getJSON(`/datasets/show/project/${dsinfo.project_id}`);
    dsinfo.pi = pdata.external_pis.filter(pi => pi.id === result.pi_id)[0];
    dsinfo.ptype_id = result.ptype_id;
    experiments = result.experiments;
    for (let key in projsamples) { delete(projsamples[key]);};
    for (let [key, val] of Object.entries(result.projsamples)) { projsamples[key] = val; }
    isNewProject = false;
  }
  if (!saved) {
    dsinfo.experiment_id = '';
  }
  editMade();
}

function toggle_project() {
  isNewProject = isNewProject === false;
}

function editMade() {
  edited = true;
  errors.basics = errors.basics.length ? validate() : [];
}

async function fetchDataset() {
  let url = '/datasets/show/info/';
  url = $dataset_id ? url + $dataset_id : url;
	const response = await getJSON(url);
  for (let [key, val] of Object.entries(response.projdata)) { pdata[key] = val; }
  for (let [key, val] of Object.entries(response.dsinfo)) { dsinfo[key] = val; }
  if ($dataset_id) {
    getcomponents();
    await project_selected(false, true); // false is event, true is saved param
    isNewExperiment = false;
    isNewPI = false;
  }
  edited = false;
}

function validate() {
	comperrors = [];
	const re = RegExp('^[a-z0-9-_]+$', 'i');
	if ((isNewProject && !dsinfo.newprojectname) || (!isNewProject && !dsinfo.project_id)) {
		comperrors.push('Project needs to be selected or created');
	}
	else if (isNewProject && dsinfo.newprojectname && !re.test(dsinfo.newprojectname)) {
		comperrors.push('Project name may only contain a-z 0-9 - _');
	}
	if (!dsinfo.runname) {
		comperrors.push('Run name is required');
	}
	else if (!re.test(dsinfo.runname)) {
		comperrors.push('Run name may only contain a-z 0-9 - _');
	}
  if (showMsdata && ((isNewExperiment && !dsinfo.newexperimentname) || (!isNewExperiment && !dsinfo.experiment_id))) {
		comperrors.push('Experiment is required');
	}
	else if (showMsdata && isNewExperiment && dsinfo.newexperimentname && !re.test(dsinfo.newexperimentname)) {
		comperrors.push('Experiment name may only contain a-z 0-9 - _');
	}
  if (isExternal) {
		if (!dsinfo.newpiname && !dsinfo.pi.id) {
			comperrors.push('Need to select or create a PI');
		}
		if (!dsinfo.externalcontactmail) {
			comperrors.push('External contact is required');
		}
	}
  // This is probably not possible to save in UI, button is disabled
	if (!dsinfo.datatype_id) {
		comperrors.push('Datatype is required');
	}
  return comperrors;
}

async function save() {
  errors.basics = validate();
  if (showMsdata) { 
    let mserrors = mssubcomp.validate();
    errors.basics = [...errors.basics, ...mserrors];
  }
  if (errors.basics.length === 0) { 
    let postdata = {
      dataset_id: $dataset_id,
      ptype_id: dsinfo.ptype_id,
      datatype_id: dsinfo.datatype_id,
      runname: dsinfo.runname,
      prefrac_id: dsinfo.prefrac_id,
      prefrac_length: dsinfo.prefrac_length,
      prefrac_amount: dsinfo.prefrac_amount,
      hiriefrange: dsinfo.hiriefrange,
    };
    if (isNewProject) {
      postdata.newprojectname = dsinfo.newprojectname;
    } else {
      postdata.project_id = dsinfo.project_id;
    }
    if (isNewExperiment) {
      postdata.newexperimentname = dsinfo.newexperimentname;
    } else {
      postdata.experiment_id = dsinfo.experiment_id;
    }
    if (isNewPI) {
      postdata.newpiname = dsinfo.newpiname;
    } else {
      postdata.pi_id = isExternal ? dsinfo.pi.id : pdata.internal_pi_id;
    }
    if (dsinfo.ptype_id !== pdata.local_ptype_id) {
      postdata.externalcontact = dsinfo.externalcontactmail;
    }
    const response = await postJSON('/datasets/save/project/', postdata);
    if ('error' in response) {
      saveerrors.basics = [response.error, ...saveerrors.basics];
    } else {
  	  dataset_id.set(response.dataset_id);
      console.log($dataset_id);
      fetchDataset();
    }
  }
}

onMount(async() => {
  await fetchDataset();
})

function showMetadata() {
  tabshow = 'meta';
}

function showFiles() {
  tabshow = $dataset_id ? 'files' : tabshow;
}

</script>


<ErrorNotif cssclass="sticky" errors={Object.values(saveerrors).flat().concat(Object.values(errors).flat())} />
<!--
{#if Object.values(errors).flat().length || Object.values(saveerrors).flat().length}
<div class="notification errorbox is-danger">
  <ul>
    {#each Object.values(saveerrors).flat() as error}
    <li>&bull; {error}</li>
    {/each}
    {#each Object.values(errors).flat() as error}
    <li>&bull; {error}</li>
    {/each}
  </ul>
</div>
{/if}
-->

<div class="tabs is-toggle is-centered is-small">
	<ul>
    <li class={tabshow === 'meta' ? 'is-active': ''}><a on:click={showMetadata}>
        <span>Metadata</span>
    </li>
    {#if $dataset_id}
    <li class={tabshow === 'files' ? 'is-active': ''}><a on:click={showFiles}>
        <span>Files</span>
    </li>
    {/if}
	</ul>
</div>

<h4 class="title is-4">Dataset</h4> 
<div style="display: {tabshow !== 'meta' ? 'none' : ''}">
    <div class="box" id="project">
    
      {#if dsinfo.storage_location}
    	<article class="message is-info"> 
        <div class="message-header">Storage location</div>
        <div class="message-body">{dsinfo.storage_location}</div>
    	</article>
      {/if}
    
      <h5 class="has-text-primary title is-5">
        {#if stored}
        <i class="icon fas fa-check-circle"></i>
        {/if}
        Basics
        <button class="button is-small is-danger has-text-weight-bold" disabled={!edited} on:click={save}>Save</button>
        <button class="button is-small is-info has-text-weight-bold" disabled={!edited || !dsinfo.datatype_id} on:click={fetchDataset}>Revert</button>
      </h5>
    
      <div class="field"> 
        <label class="label">Project
          <a class="button is-danger is-outlined is-small" on:click={toggle_project}>
            {#if isNewProject}
            Use existing project
            {:else}
            Create new project
            {/if}
          </a>
        </label>
        <div class="control">
        {#if !isNewProject}
          <div class="select">
            <select bind:value={dsinfo.project_id} on:change={project_selected}>
              <option disabled value="">Please select one</option>
              {#each pdata.projects as project}
              <option value={project.id}>{project.name}</option>
              {/each}
            </select>
          </div>
        {:else}
        <input class="input" bind:value={dsinfo.newprojectname} type="text" placeholder="Project name" on:change={editMade}>
        <label class="label">Project type</label>
        <div class="select">
          <select bind:value={dsinfo.ptype_id}>
            <option disabled value="">Please select one</option>
            {#each pdata.ptypes as ptype}
            <option value={ptype.id}>{ptype.name}</option>
            {/each}
          </select>
        </div>
        {/if}
        {#if isExternal}
        <span class="tag is-success is-medium">External project: {dsinfo.pi.name}</span>
        {/if}
        </div>
      </div>

      {#if isExternal}
      <div class="field">
        <label class="label">contact(s)
          {#if isNewProject && isNewPI}
          <a class="button is-danger is-outlined is-small" on:click={e => isNewPI = !isNewPI}>Use existing PI</a>
          {:else if isNewProject}
          <a class="button is-danger is-outlined is-small" on:click={e => isNewPI = !isNewPI}>Create new PI</a>
          {/if}
        </label>
        {#if isNewProject && !isNewPI}
        <div class="control">
          <div class="select">
            <select on:change={editMade} bind:value={dsinfo.pi}>
					  	<option disabled value="">Please select one</option>
              {#each pdata.external_pis as expi}
              <option value={expi}>{expi.name}</option>
              {/each}
					  </select>
				  </div>
			  </div>
        {:else if isNewProject}
        <div class="control">
          <input class="input" on:input={editMade} bind:value={dsinfo.newpiname} type="text" placeholder="PI name">
        </div>
        {/if}
        <div class="control">
          <input class="input" type="text" on:change={editMade} bind:value={dsinfo.externalcontactmail} placeholder="operational contact email (e.g. postdoc)">
        </div>
      </div>
      {/if}
    
      <div class="field">
        <label class="label">Dataset type</label>
        <div class="control">
          <div class="select">
            <select bind:value={dsinfo.datatype_id} on:change={getcomponents}>
              <option disabled value="">Please select one</option>
              {#each pdata.datasettypes as dstype}
              <option value={dstype.id}>{dstype.name}</option>
              {/each}
            </select>
          </div>
        </div>
      </div>

      {#if showMsdata}
      <Msdata bind:this={mssubcomp} on:edited={editMade} bind:dsinfo={dsinfo} bind:isNewExperiment={isNewExperiment} experiments={experiments} prefracs={pdata.prefracs} hirief_ranges={pdata.hirief_ranges} />

      <div class="field">
        <label class="label">Run name</label>
        <div class="control">
          <input class="input" bind:value={dsinfo.runname} on:change={editMade} type="text" placeholder="E.g set1, lc3, rerun5b, etc">
        </div>
      </div>

      <Acquicomp bind:this={acquicomp} bind:errors={errors.acqui} />
      {:else if dsinfo.datatype_id}
      <div class="field">
        <label class="label">Run name</label>
        <div class="control">
          <input class="input" bind:value={dsinfo.runname} on:change={editMade} type="text" placeholder="E.g set1, lc3, rerun5b, etc">
        </div>
      </div>
      {/if}
      {#if (components.indexOf('sampleprep')> -1)}
      <Prepcomp bind:this={prepcomp} bind:errors={errors.sprep} />
      {/if}
      {#if (Object.keys($datasetFiles).length && components.indexOf('labelchecksamples')>-1)}
      <LCheck bind:this={lccomp} bind:errors={errors.lc} />
      {:else if (Object.keys($datasetFiles).length && components.indexOf('pooledlabelchecksamples')>-1)}
      <Prepcomp bind:this={prepcomp} bind:errors={errors.lc} />
      {/if}
    </div>
</div>

<div style="display: {tabshow !== 'files' ? 'none' : ''}">
    <Files bind:this={filescomp} />
</div>
