<script>

import { onMount } from 'svelte';
import { flashtime } from '../../util.js'
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'

let notif = {errors: {}, messages: {}, links: {}};
let loadingItems = false;

let runButtonActive = true;
let postingAnalysis = false;

let allwfs = {};
let wf = false;
let wforder = [];
let dsets = {};

/* API v1:
- no mixed isobaric
- no mixed instruments
- mixed dtype is ok i guess, but stupid
- use invisible flags (check that stuff, deqmspossible, nf1901, nf-coremarker: could ALL be removed?)
  Can at least remove from passing to NF pipe
- isobaric passing to pipeline in a certain way (flags, sets etc)
- predefined files in old version
- version switcher for new version
 
Test
- normal hirief
- labelfree?
- filesaresets (eg LG)
- labelcheck
- 6FT, vardb
- nf-core version config
*/

// API v1 instype is not important in v2

let isoquants = {};
let mediansweep = false;

let multicheck = [];
let config = {
  wfid: false,
  wfversion: false,
  analysisname: '',
  flags: [],
  fileparams: {},
  inputparams: {},
  multifileparams: {},
  v1: false,
  v2: false,
  version_dep: {
    v1: {
      instype: false,
      dtype: false,
    }
  },
}
let matchedFr = {};
let frregex = {};

function validate() {
  notif = {errors: {}, messages: {}, links: {}};
  const charRe = RegExp('^[a-z0-9_-]+$', 'i');
  if (!config.analysisname) {
	  notif.errors['Analysisname must be filled in'] = 1;
	} else if (!charRe.test(config.analysisname)) {
		notif.errors['Analysisname may only contain a-z 0-9 _ -'] = 1;
	}
	if (!config.wfid) {
		notif.errors['You must select a workflow'] = 1;
	}
  if (!config.wfversion) {
		notif.errors['You must select a workflow version'] = 1;
	}
  Object.values(dsets).forEach(ds => {
    if (config.version_dep.v1.dtype.toLowerCase() !== 'labelcheck' && !ds.filesaresets && !ds.setname) {
			notif.errors[`Dataset ${ds.proj} - ${ds.exp} - ${ds.run} needs to have a set name`] = 1;
    } else if (ds.filesaresets) {
      if (ds.files.filter(fn => !fn.setname).length) {
			  notif.errors[`File ${fn.name} needs to have a setname`] = 1;
			}
    } else if (ds.setname && !charRe.test(ds.setname)) {
			notif.errors[`Dataset ${ds.proj} - ${ds.exp} - ${ds.run} needs to have another set name: only a-z 0-9 _ are allowed`] = 1;
		}
	});
  Object.entries(isoquants).forEach(([sname, isoq]) => {
    Object.entries(isoq.samplegroups).forEach(([ch, sgroup]) => {
      if (sgroup && !charRe.test(sgroup)) {
        notif.errors[`Incorrect sample group name for set ${sname}, channel ${ch}, only A-Z a-z 0-9 _ are allowed`] =1; 
      }
    })
  })
  return Object.keys(notif.errors).length === 0;
}


async function runAnalysis() {
  if (!validate()) {
  	return false;
  }
  runButtonActive = false;
  postingAnalysis = true;
  notif.messages['Validated data'] = 1;
  let fns = Object.fromEntries(Object.entries(config.fileparams).filter(([k,v]) => v))
  wf.fixedfileparams.forEach(fn => {
    fns[fn.nf] = fn.id
  })
  let multifns = Object.fromEntries(Object.entries(config.multifileparams).map(([k, v]) => [k, Object.values(v).filter(x => x)]).filter(([k, v]) => v.length));
  let setnames = {};
  Object.values(dsets).filter(ds => ds.filesaresets).forEach(ds => {
    Object.assign(setnames, Object.fromEntries(ds.files.map(fn => [fn.id, fn.setname])));
  });
  Object.values(dsets).filter(ds => !ds.filesaresets).forEach(ds => {
    Object.assign(setnames, Object.fromEntries(ds.files.map(fn => [fn.id, ds.setname])));
  });

  const fractions = Object.fromEntries(Object.values(dsets).flatMap(ds => ds.files.map(fn => [fn.id, fn.fr])));

  notif.messages[`${Object.keys(setnames).length} set(s) found`] = 1;
  notif.messages[`Using ${Object.keys(dsets).length} dataset(s)`] = 1;
  notif.messages[`${Object.keys(fns).length} other inputfiles found`];
  let post = { 
    setnames: setnames,
    dsids: Object.keys(dsets),
    fractions: fractions,
    singlefiles: fns,
    multifiles: multifns,
    wfid: config.wfid,
    nfwfvid: config.wfversion.id,
    analysisname: `${allwfs[config.wfid].wftype}_${config.analysisname}`,
    strips: {},
    params: {
      flags: config.flags,
      inputparams: Object.entries(config.inputparams).filter(([k,v]) => v).flat(),
      multi: multicheck.reduce((acc, x) => {acc[x[0]].push(x[1]); return acc}, Object.fromEntries(multicheck.map(x => [x[0], []]))),
    },
  };
  if (config.v1) {
    post.params.inst = ['--instrument', config.version_dep.v1.instype];
    post.params.quant = config.version_dep.v1.qtype === 'labelfree' ? [] : ['--isobaric', config.version_dep.v1.qtype];
  }
  // HiRIEF
  Object.values(dsets).forEach(ds => {
    post.strips[ds.id] = ds.hr ? ds.hr : ds.prefrac ? 'unknown_plate' : false
  })
  // general denoms = [[set1, [126, 127], tmt10plex], [set2, [128, 129], tmt6plex]]
  let denoms = Object.entries(isoquants).map(([sname, isoq]) => 
    [sname, Object.entries(isoq.denoms).filter(([ch, val]) => val).map(([ch, val]) => ch), isoq.chemistry]
   )
  // TODO This filters sets without denoms, possibly change this for when not using any (e.g. intensities instead)
  if (!mediansweep && denoms.filter(([sn, chs, chem]) => !chs.length)) {
    notif.errors['Median sweep not used but not all sets have denominator, cannot run this'] = 1;
  }
  // mediansweep is only active at 1-set analyses, otherwise it is supposed to not make sense, so we can have global flag
  if (denoms.length && !mediansweep && config.v1) {
    // API v1: denoms: 'set1:126:127 set2:128:129'
    post.params.denoms = ['--denoms', denoms.map(([sname, chs, chem]) => `${sname}:${chs.join(':')}`).join(' ')];
  } else if (denoms.length && !mediansweep && !config.v1) {
    // API v2: isobaric: 'set1:tmt10plex:126:127 set2:itraq8plex:114'
    post.params.denoms = ['--isobaric', denoms.map(([sname, chs, chem]) => `${sname}:${chem}:${chs.join(':')}`).join(' ')];
  } else if (mediansweep) {
    post.params.denoms = ['--isobaric', `${denoms[0][0]}:${denoms[0][2]}:sweep`];
  }

  // sampletable [[ch, sname, groupname], [ch2, sname, samplename, groupname], ...]
  // we can push sampletables on ANY workflow as nextflow will ignore non-params
  let sampletable = Object.entries(isoquants).flatMap(([sname, isoq]) => 
    Object.entries(isoq.channels).map(([ch, sample]) => [ch, sname, sample, isoq.samplegroups[ch]]).sort((a, b) => {
	  return a[0].replace('N', 'A') > b[0].replace('N', 'A')
    })
  );
  post.sampletable = sampletable.map(row => row.slice(0, 3).concat(row[3] ? row[3] : 'X__POOL'));
   
  // Post the payload
  if (!Object.entries(notif.errors).filter(([k,v]) => v).length) {
    notif.messages[`Posting analysis job for ${this.analysisname}`] = 1;
    const resp = await postJSON('/analysis/run/', post);
    if (resp.error) {
      notif.errors[resp.error] = 1;
      if ('link' in resp) {
        notif.links[resp.link] = 1;
      }
    } else {
      window.location.href = '/?tab=searches';
    }
  }
  postingAnalysis = false;
  runButtonActive = true;
}


async function fetchWorkflow() {
  let url = new URL('/analysis/workflow', document.location)
  const params = {dsids: dsids.join(','), wfvid: config.wfversion.id};
  url.search = new URLSearchParams(params).toString();
  const result = await getJSON(url);
  loadingItems = true;
  if ('error' in result) {
    const msg = `While fetching workflow versions, encountered: ${result.error}`;
    notif.errors[msg] = 1;
    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
  } else {
    wf = result['wf'];
    config.v1 = wf.analysisapi === 1;
    config.v2 = wf.analysisapi === 2;
  }
  if (wf.multifileparams.length) {
    config.multifileparams = Object.fromEntries(wf.multifileparams.map(x => [x.nf, {0: ''}]));
  }
  fetchDatasetDetails();
}

async function fetchAllWorkflows() {
  let url = new URL('/analysis/workflows', document.location)
  const result = await getJSON(url);
  loadingItems = true;
  if ('error' in result) {
    const msg = `While fetching workflows, encountered: ${result.error}`;
    notif.errors[msg] = 1;
    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
  } else {
    allwfs = result.allwfs;
    wforder = result.order;
  }
}

async function fetchDatasetDetails() {
  let url = new URL('/analysis/dsets/', document.location)
  const params = {dsids: dsids.join(',')};
  url.search = new URLSearchParams(params).toString();
  const result = await getJSON(url);
  if (result.error) {
    const msg = result.errmsg;
    notif.errors[msg] = 1;
    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
  } else {
    dsets = result.dsets;
    Object.entries(dsets).filter(x=>x[1].prefrac).forEach(x=>matchFractions(dsets[x[0]]));
    Object.entries(dsets).forEach(ds => {
      ds.filesaresets = false;
      ds.setname = '';
    })
    // API v1 stuff
    const dtypes = new Set(Object.values(dsets).map(ds => ds.dtype.toLowerCase()));
    config.version_dep.v1.dtype = dtypes.size > 1 ? 'mixed' : dtypes.keys().next().value;
    const qtypes = new Set(Object.values(dsets).map(ds => ds.details.qtypeshort));
    if (config.v1 && qtypes.size > 1) {
      notif.errors['Mixed quant types detected, cannot use those in single run, use more advanced pipeline version'] = 1;
    } else {
      config.version_dep.v1.qtype = qtypes.keys().next().value;
    }
    const instypes = new Set(Object.values(dsets).flatMap(ds => ds.details.instrument_types).map(x => x.toLowerCase()));
    if (config.v1 && instypes.size> 1) {
      notif.errors['Mixed instrument types detected, cannot use those in single run, use more advanced pipeline version'] = 1;
    } else {
      config.version_dep.v1.instype = instypes.keys().next().value;
    }
  }
}

function removeMultifile(nf, key) {
  delete(config.multifileparams[nf][key]);
  let newmfp = {}
  Object.keys(config.multifileparams[nf]).forEach((k, ix) => {
    newmfp[ix] = config.multifileparams[nf][k]
  });
  config.multifileparams[nf] = newmfp;
}

function addMultifile(nf) {
  const keyints = Object.keys(config.multifileparams[nf]).map(x => +x);
  const newkey = keyints.length ? Math.max(...keyints) + 1 : 0;
  config.multifileparams[nf][newkey] = '';
}

function matchFractions(ds) {
  let allfrs = new Set();
  for (let fn of ds.files) {
    const match = fn.name.match(RegExp(frregex[ds.id]));
    if (match) {
      fn.fr = match[1];
      allfrs.add(match[1]);
    } else {
      fn.fr = 'NA';
    }
  }
	matchedFr[ds.id] = allfrs.size;
}

function sortChannels(channels) {
  return Object.entries(channels).sort((a,b) => {
	  return a[0].replace('N', 'A') > b[0].replace('N', 'A')
  }).map(x => {return {ch: x[0], sample: x[1]}});
}

function updateIsoquant() {
  // Add new set things if necessary
  Object.values(dsets).forEach(ds => {
    const errmsg = `Sample set mixing error! Channels for datasets with setname ${ds.setname} are not identical!`;
    notif.errors[errmsg] = 0;
    if (ds.setname && !(ds.setname in isoquants)) {
      isoquants[ds.setname] = {
        chemistry: ds.details.qtypeshort,
        channels: ds.details.channels,
        samplegroups: Object.fromEntries(Object.keys(ds.details.channels).map(x => [x, ''])),
        denoms: Object.fromEntries(Object.keys(ds.details.channels).map(x => [x, false]))
      };
    } else if (ds.setname && ds.setname in isoquants) {
      if (isoquants[ds.setname].channels !== ds.details.channels) {
        notif.errors[errmsg] = 1;
      }
    }
  });
  // Remove old sets from isoquants if necessary
  const dset_sets = new Set(Object.values(dsets).map(ds => ds.setname).filter(x => x));
  Object.keys(isoquants).filter(x => !(dset_sets.has(x))).forEach(x => {
    delete(isoquants[x])
  });
  isoquants = Object.assign({}, isoquants);  // assign so svelte notices (doesnt act on deletion)
}

onMount(async() => {
  frregex = Object.fromEntries(dsids.map(dsid => [dsid, '.*fr([0-9]+).*mzML$']));
  fetchAllWorkflows();
})
</script>

<style>
.errormsg {
  position: -webkit-sticky;
  position: sticky;
  top: 20px;
  z-index: 50000;
}
</style>

<div class="errormsg">
{#if Object.values(notif.errors).some(x => x === 1)}
<div class="notification is-danger is-light"> 
    {#each Object.entries(notif.errors).filter(x => x[1] == 1).map(x=>x[0]) as error}
    <div>{error}</div>
    {/each}
</div>
{/if}

{#if Object.values(notif.links).some(x => x === 1)}
<div class="notification is-danger is-light errormsg"> 
    {#each Object.entries(notif.links).filter(x => x[1] == 1).map(x=>x[0]) as link}
    <div>Click here: <a target="_blank" href={link}>here</a></div>
    {/each}
</div>
{/if}

{#if Object.values(notif.messages).some(x => x === 1)}
<div class="notification is-success is-light errormsg"> 
    {#each Object.entries(notif.messages).filter(x => x[1] == 1).map(x=>x[0]) as message}
    <div>{message}</div>
    {/each}
</div>
{/if}
</div>

<div class="content">
	<div class="title is-5">Analysis </div>
	<div class="field is-horizontal">
    <div class="field-label is-normal">
      <label class="label">Workflow:</label>
    </div>
    <div class="field-body">
      <div class="field">
        <div class="select">
          <select bind:value={config.wfid} on:change={e => wf = config.wfversion = false}>
            <option disabled value={false}>Select workflow</option>
            {#each wforder as wfid}
            <option value={wfid}>{allwfs[wfid].name} </option>
            {/each}
          </select>
        </div>
      </div>
    </div>
    <div class="field-label is-normal">
      <label class="label">Workflow version:</label>
    </div>
    <div class="field-body">
      <div class="field">
        <div class="select" on:change={fetchWorkflow}>
          <select bind:value={config.wfversion}>
            <option disabled value={false}>Select workflow version</option>
            {#if config.wfid}
            {#each allwfs[config.wfid].versions as wfv}
            <option value={wfv}>
              {#if wfv.latest}
              <span>LATEST: </span>
              {/if}
              {wfv.date} -- {wfv.name}
            </option>
            {/each}
            {/if}
          </select>
        </div>
      </div>
    </div>
	</div>


  {#if wf}
	<div class="field">
    <input type="text" class="input" bind:value={config.analysisname} placeholder="Please enter analysis name">
    <div>Full name will be <code>{allwfs[config.wfid].wftype}_{config.analysisname}</code>
    This will be the folder name for the output and prefixed to the output filenames
    </div>
	</div>

  <!-------------------------- ############### API v1? -->
	<div class="title is-5">Datasets</div>
  {#each Object.values(dsets) as ds}
  <div class="box">
    {#if ds.dtype.toLowerCase() === 'labelcheck'}
    <span class="has-text-primary">{ds.proj} // Labelcheck // {ds.run} // {ds.details.qtype} // {ds.details.instruments.join(',')}</span>
    {:else}
		<div class="columns">
		  <div class="column">
        {#if !ds.prefrac}
        <input type="checkbox" bind:checked={ds.filesaresets}>
				<label class="checkbox">Each file is a different sample</label>
        {/if}
        {#if !ds.filesaresets}
			  <div class="field">
          <input type="text" class="input" placeholder="Name of set" bind:value={ds.setname} on:change={updateIsoquant}>
			  </div>
        {/if}
			  <div class="subtitle is-6 has-text-primary">
          <span>{ds.proj} // {ds.exp} // {ds.run} //</span>
          {#if !ds.prefrac}
          <span>{ds.dtype}</span>
          {:else if ds.hr}
          <span>{ds.hr}</span>
          {:else}
          <span>{ds.prefrac}</span>
          {/if}
			  </div>
			  <div class="subtitle is-6">
				  <span>{ds.details.qtype} </span>
          {#each Object.entries(ds.details.nrstoredfiles) as sf}
		      <span> // {sf[1]} {sf[0]} files </span>
          {/each}
				  <span>// {ds.details.instruments.join(', ')} </span>
			  </div>
        {#if ds.details.nrstoredfiles.refined_mzML}
			  <div class="subtitle is-6"><strong>Enforcing use of refined mzML(s)</strong></div>
        {/if}
			</div>
			<div class="column">
        {#if ds.prefrac}
        <div class="field">
					<label class="label">Regex for fraction detection</label>
          <input type="text" class="input" on:change={e => matchFractions(ds)} bind:value={frregex[ds.id]}>
				</div>
				<span>{matchedFr[ds.id]} fractions matched</span>
        {/if}
			</div>
		</div>
    {#if ds.filesaresets}
    {#each ds.files as fn}
    <div class="columns">
		  <div class="column">{fn.name}</div>
		  <div class="column">
        <input type="text" class="input" bind:value={fn.setname} placeholder={fn.sample}>
			</div>
		</div>
    {/each}
    {/if}
    {/if}
  </div>
  {/each}

  {#if Object.keys(isoquants).length}
  <div class="box">
		<div class="title is-5">Isobaric quantification</div>
    {#if Object.keys(isoquants).length === 1}
    <div class="field">
      <input type="checkbox" bind:checked={mediansweep}>
      <label class="checkbox">Use median sweeping (no predefined denominators)
        <span class="icon is-small">
          <a title="Pick median denominator per PSM, only for single-set analyses"><i class="fa fa-question-circle"></i></a>
        </span>
      </label>
    </div>
    {/if}
    {#each Object.entries(isoquants) as isoq}
    <div class="has-text-primary title is-6">Set: {isoq[0]}</div>
    <div class="columns">
      <div class="column is-three-quarters">
        <table class="table is-striped is-narrow">
          <thead>
            <tr>
              {#if !mediansweep}
              <th>Denominator</th>
              {:else}
              <th><del>Denominator</del></th>
              {/if}
              <th>Channel</th>
              <th>Sample name</th>
              <th>Sample group 
                <span class="icon is-small">
                  <a title="For DEqMS and PCA plots"><i class="fa fa-question-circle"></i></a>
                </span>
                LEAVE EMPTY FOR INTERNAL STANDARDS!</th>
      		  </tr>
          </thead>
          <tbody>
            {#each sortChannels(isoq[1].channels) as {ch, sample}}
            <tr>
              <td>
                {#if !mediansweep}
                <input type="checkbox" bind:checked={isoq[1].denoms[ch]} />
                {/if}
              </td>
              <td>{ch}</td>
              <td>{sample}</td>
              <td>
                <input type="text" class="input" bind:value={isoq[1].samplegroups[ch]} placeholder="Sample group or empty (e.g. CTRL, TREAT)">
              </td>
      		  </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
    {/each}
  </div>
  {/if}

  <div class="box">
    <div class="title is-5">Workflow parameters</div>
    {#each wf.multicheck as {nf, name, opts}}
    <div class="field">
      <label class="label">{name} <code>{nf}</code></label> 
      {#each Object.entries(opts) as opt}
      <div>
        <input value={[nf, opt[0]]} bind:group={multicheck} type="checkbox">
        <label class="checkbox">{opt[1]}</label>
      </div>
      {/each}
    </div>
    {/each}

    {#each wf.numparams as {nf, name, type}}
    <div class="field">
      <label class="label">{name} <code>{nf}</code></label> 
      <input type="number" class="input" bind:value={config.inputparams[nf]}>
    </div>
    {/each}

    <label class="label">Config flags</label>
    {#each wf.flags as {nf, name}}
    <div>
      <input value={nf} bind:group={config.flags} type="checkbox">
      <label class="checkbox">{name}</label>: <code>{nf}</code>
    </div>
    {/each}

	</div>

  <div class="box">
    <div class="title is-5">Input files</div>
    {#each wf.multifileparams as filep}
      <label class="label">{filep.name}
        <span class="icon is-small">
          <a on:click={e => addMultifile(filep.nf)} title="Add another file"><i class="fa fa-plus-square"></i></a>
        </span>
      </label>
      {#each Object.keys(config.multifileparams[filep.nf]) as mfpkey}
      <label class="label is-small">
        File nr. {mfpkey} 
        <span class="icon is-small">
          <a on:click={e => removeMultifile(filep.nf, mfpkey)} title="Remove this file"><i class="fa fa-trash-alt"></i></a>
        </span>
      </label>
        <div class="field">
            <div class="select">
              <select bind:value={config.multifileparams[filep.nf][mfpkey]}>
                <option disabled value="">Please select one</option>
                <option value="">Do not use this parameter</option>
                {#if filep.ftype in wf.libfiles}
                {#each wf.libfiles[filep.ftype] as libfn}
                <option value={libfn.id}>{libfn.name} -- {libfn.desc}</option>
                {/each}
                {/if}
                {#if filep.allow_resultfile}
                {#each wf.prev_resultfiles as resfile}
                <option value={resfile.id}>{resfile.analysisname} -- {resfile.analysisdate} -- {resfile.name}</option>
                {/each}
                {/if}
              </select>
            </div>
              </div>
      {/each}
    {/each}
    {#each wf.fileparams as filep}
    <div class="field">
      <label class="label">{filep.name}</label>
      <div class="select">
        <select bind:value={config.fileparams[filep.nf]}>
          <option disabled value="">Please select one</option>
          <option value="">Do not use this parameter</option>
          {#if filep.ftype in wf.libfiles}
          {#each wf.libfiles[filep.ftype] as libfn}
          <option value={libfn.id}>{libfn.name} -- {libfn.desc}</option>
          {/each}
          {/if}
          {#if filep.allow_resultfile}
          {#each wf.prev_resultfiles as resfile}
          <option value={resfile.id}>{resfile.analysisname} -- {resfile.analysisdate} -- {resfile.name}</option>
          {/each}
          {/if}
        </select>
      </div>
    </div>
    {/each}
	</div>

  {#if wf.fixedfileparams.length}
	<div class="box">
    <div class="title is-5">Predefined files</div>
    {#each wf.fixedfileparams as ffilep}
    <div class="field">
      <label class="label">{ffilep.name}</label>
      <div class="select" >
        <select>
          <option disabled value="">Fixed selection</option>
          <option>{ffilep.fn} -- {ffilep.desc}</option>
        </select>
      </div>
    </div>
    {/each}
  </div>
  {/if}

  {#if runButtonActive}
  <a class="button is-primary" on:click={runAnalysis}>Run analysis</a>
  {:else if postingAnalysis}
	<a class="button is-primary is-loading">Run analysis</a>
  {:else}
	<a class="button is-primary" disabled>Run analysis</a>
  {/if}

  {/if} 
</div>
