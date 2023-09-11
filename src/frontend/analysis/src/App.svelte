<script>
/* TODO
- loadable/edit analysis
- button store, button store+run
- click-removable datasets ?
- 
*/

import { onMount } from 'svelte';
import { flashtime } from '../../util.js'
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'
import DynamicSelect from '../../datasets/src/DynamicSelect.svelte';

let notif = {errors: {}, messages: {}, links: {}};
let loadingItems = false;

let runButtonActive = true;
let postingAnalysis = false;

let analysis_id = existing_analysis ? existing_analysis.analysis_id : false;
let allwfs = {};
let wf = false;
let wforder = [];
let dsets = {};

let libfiles = {};
let libfnorder = [];
let fetched_resultfiles = [];
let prev_resultfiles = [];
let resfn_arr = [];
let resultfiles = {}
let resultfnorder = [];

let base_analysis = {
  isComplement: false,
  dsets_identical: false,
  selected: false,
  typedname: '',
  fetched: {},
  resultfiles: [],
}

let adding_analysis = {
  selected: false,
  typedname: '',
  fetched: {},
}

let added_analyses_order = [];
let added_results = {};
if (existing_analysis && existing_analysis.added_results) {
  added_results = existing_analysis.added_results;
  added_analyses_order = Object.keys(existing_analysis.added_results);
}

$: {
  fetched_resultfiles = added_analyses_order.flatMap(x => added_results[x].fns);
  resfn_arr = fetched_resultfiles.concat(base_analysis.resultfiles).concat(prev_resultfiles);
  resultfiles = Object.fromEntries(resfn_arr.map(x=> [x.id, x]));
  resultfnorder = resfn_arr.map(x => x.id);
}

/*
NF workflow API v1:
- no mixed isobaric
- no mixed instruments
- mixed dtype is ok i guess, but stupid
- predefined files exist
- isobaric spec as --isobaric tmt10plex --denoms set1:126 set2:127N
 
NF workflow API v2:
- mods / locptms via multi-checkbox
- DBs via multi-file interface
- isobaric spec as --isobaric set1:tmt10plex:126 set2:6plex:sweep
*/


let config = {
  wfid: false,
  wfversion: false,
  analysisname: '',
  flags: [],
  multicheck: [],
  isoquants: {},
  fileparams: {},
  inputparams: {},
  multifileparams: {},
  mzmldef: false,
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
  if (!Object.keys(dsets).length) {
    notif.errors['No datasets are in this analysis, maybe they need some editing'] = 1;
  }
  if ('mzmldef' in wf.components && !config.mzmldef) {
		notif.errors['You must select a mzml definition file'] = 1;
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
  Object.entries(config.isoquants).forEach(([sname, isoq]) => {
    if (!('labelcheck' in wf.components) && !isoq.report_intensity && !isoq.sweep && !Object.values(isoq.denoms).filter(x => x).length) {
      notif.errors[`No denominator, sweep or intensity values are filled in for set ${sname}`] = 1;
    }
    Object.entries(isoq.samplegroups).forEach(([ch, sgroup]) => {
      if (sgroup && !charRe.test(sgroup)) {
        notif.errors[`Incorrect sample group name for set ${sname}, channel ${ch}, only A-Z a-z 0-9 _ are allowed`] =1; 
      }
    })
  })
  return Object.keys(notif.errors).length === 0;
}


async function storeAnalysis() {
  if (!validate()) {
  	return false;
  }
  runButtonActive = false;
  postingAnalysis = true;
  notif.messages['Validated data'] = 1;
  let fns = Object.fromEntries(Object.entries(config.fileparams).filter(([k,v]) => v))
  wf.fixedfileparams.forEach(fn => {
    fns[fn.id] = fn.sfid
  })
  let multifns = Object.fromEntries(Object.entries(config.multifileparams).map(([k, v]) => [k, Object.values(v).filter(x => x)]).filter(([k, v]) => v.length));

  notif.messages[`Using ${Object.keys(dsets).length} dataset(s)`] = 1;
  notif.messages[`${Object.keys(fns).length} other inputfiles found`];
  let post = {
    analysis_id: analysis_id,
    base_analysis: base_analysis,
    dsids: Object.keys(dsets),
    dssetnames: Object.fromEntries(Object.entries(dsets).filter(([x,ds]) => !ds.filesaresets).map(([dsid, ds]) => [dsid, ds.setname])),
    fractions: Object.fromEntries(Object.values(dsets).flatMap(ds => ds.files.map(fn => [fn.id, fn.fr]))),
    fnsetnames: Object.fromEntries(Object.entries(dsets).filter(([x,ds]) => ds.filesaresets).map(
      ([dsid, ds]) => ds.files.map(fn => [fn.id, fn.setname])).flat()),
    frregex: Object.fromEntries(Object.entries(dsets).map(([dsid, ds]) => [dsid, ds.frregex])),
    singlefiles: fns,
    multifiles: multifns,
    components: {
      mzmldef: config.mzmldef,
      sampletable: false,
    },
    wfid: config.wfid,
    nfwfvid: config.wfversion.id,
    analysisname: config.analysisname,
    isoquant: {},
    params: {
      flags: Object.fromEntries(config.flags.map(x => [x, true])),
      inputparams: config.inputparams,
      multicheck: config.multicheck.reduce((acc, x) => {
        const xspl = x.split('___');
        acc[xspl[0]].push(xspl[1]);
        return acc},
        Object.fromEntries(config.multicheck.map(x => {
          const xspl = x.split('___');
          return [xspl[0], []]
        }))),
    },
  };
  if (config.v1) {
    post.params.inst = ['--instrument', config.version_dep.v1.instype];
  }
  if ('isobaric_quant' in wf.components) {
    post.isoquant = config.isoquants;
  }

  if ('isobaric_quant' in wf.components || 'sampletable' in wf.components) {
    // sampletable [[ch, sname, groupname], [ch2, sname, samplename, groupname], ...]
    // we can push sampletables on ANY workflow as nextflow will ignore non-params
    const sampletable = Object.entries(config.isoquants).flatMap(([sname, isoq]) => 
      Object.entries(isoq.channels).map(([ch, sample]) => [ch, sname, sample[0], isoq.samplegroups[ch]]).sort((a, b) => {
      return a[0].replace('N', 'A') > b[0].replace('N', 'A')
      })
    );
    post.components.sampletable = sampletable;
  }
   
  // Post the payload
  if (!Object.entries(notif.errors).filter(([k,v]) => v).length) {
    notif.messages[`Storing analysis for ${config.analysisname}`] = 1;
    const resp = await postJSON('/analysis/store/', post);
    if (resp.error) {
      notif.errors[resp.error] = 1;
      if ('link' in resp) {
        notif.links[resp.link] = 1;
      }
      if ('files_nods' in resp) {
        // Dsets have been changed while editing analysis
        const files_nodset = new Set(resp.files_nods);
        Object.values(dsets).filter(ds => files_nodset.intersect(Object.values(ds.files).map(x => x.id))).forEach(ds => {
          ds.changed = true;
        });
        Object.entries(dsets).filter(([dsid, ds]) => resp.ds_newfiles.indexOf(dsid) > -1).forEach(([dsid, ds]) => {
          ds.changed = true;
        });
      }
    } else {
      analysis_id = resp.analysis_id;
    }
  }
  postingAnalysis = false;
  runButtonActive = true;
}


async function runAnalysis() {
  await storeAnalysis();
  if (!Object.entries(notif.errors).filter(([k,v]) => v).length) {
    notif.messages[`Queueing analysis job for ${config.analysisname}`] = 1;
    const post = {
      analysis_id: analysis_id,
    }
    const resp = await postJSON('/analysis/start/', post);
    if (resp.error) {
      notif.errors[resp.error] = 1;
    } else {
      window.location.href = '/?tab=searches';
    }
  }
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
    libfiles = Object.fromEntries(Object.entries(result.wf.libfiles).map(([ft, lf]) => [ft, Object.fromEntries(lf.map(x => [x.id, x]))]));
    libfnorder = Object.fromEntries(Object.entries(result.wf.libfiles).map(([ft, lf]) => [ft, lf.map(x => x.id)]));
    prev_resultfiles = result.wf.prev_resultfiles;
    wf = result.wf;
    config.v1 = wf.analysisapi === 1;
    config.v2 = wf.analysisapi === 2;
  }
  if (wf.multifileparams.length) {
    config.multifileparams = Object.assign(config.multifileparams, Object.fromEntries(wf.multifileparams.filter(x => !(x.id in config.multifileparams)).map(x => [x.id, {0: ''}])));
  }
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

async function fetchDatasetDetails(fetchdsids) {
  let url = new URL('/analysis/dsets/', document.location)
  const params = {
    dsids: fetchdsids ? fetchdsids.join(',') : dsids.join(','),
    anid: existing_analysis ? existing_analysis.analysis_id : 0,
  };
  url.search = new URLSearchParams(params).toString();
  const result = await getJSON(url);
  if (result.error) {
    const msg = result.errmsg.join('<br>');
    notif.errors[msg] = 1;
    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
  } else {
    Object.keys(result.dsets).forEach(x => {
      dsets[x] = result.dsets[x];
      dsets[x].changed = false;
      });
    Object.keys(dsets).forEach(x => {
      dsets[x].changed = false;
    })
    Object.entries(dsets).filter(x=>x[1].prefrac).forEach(x=>matchFractions(dsets[x[0]]));
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


async function loadAnalysisResults() {
  if (added_analyses_order.indexOf(adding_analysis.selected) > -1) {
    return;
  }
  let url = new URL(`/analysis/resultfiles/load/${adding_analysis.selected}/`, document.location)
  const params = {
    dsids: dsids.join(','),
    base_ana: base_analysis.selected || '0',
  };
  url.search = new URLSearchParams(params).toString();
  const result = await getJSON(url);
  if ('error' in result) {
    const msg = `While fetching analysis, encountered: ${result.error}`;
    notif.errors[msg] = 1;
    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
  } else {
    added_analyses_order.push(adding_analysis.selected);
    added_results[adding_analysis.selected] = result;
  }
}


function removeAnalysisResults(anaid) {
  if (added_analyses_order.indexOf(anaid) === -1) {
    return
  }
  added_analyses_order = added_analyses_order.filter(x => x !== anaid);
  delete(added_results[anaid]);
  added_results = added_results;
}


async function loadBaseAnalysis() {
  /*
    Load fresh base analysis (resetting its isComplement/runFromPSM also)
    */
  const params = {
    dsids: Object.keys(dsets).join(','),
    added_ana_ids: Object.keys(added_results).join(','),
  }
  let url = new URL(`/analysis/baseanalysis/load/${config.wfversion.id}/${base_analysis.selected}/`, document.location);
  url.search = new URLSearchParams(params).toString();
  const result = await getJSON(url);
  if ('error' in result) {
    const msg = `While fetching base analysis, encountered: ${result.error}`;
    notif.errors[msg] = 1;
    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
  } else {
    base_analysis.resultfiles = result.resultfiles;
    base_analysis.dsets_identical = result.base_analysis.dsets_identical;
    for (const key of ['runFromPSM', 'isComplement']) {
      base_analysis[key] = false;
    }
    base_analysis = base_analysis;
    let overlapping_setnames = new Set();
    for (const dsid in result.datasets) {
      if (dsid in dsets) {
        dsets[dsid].setname = result.datasets[dsid].setname;
        overlapping_setnames.add(dsets[dsid].setname);
        dsets[dsid].frregex = result.datasets[dsid].frregex;
      }
    }
    for (const sname in result.base_analysis.isoquants) {
      if (overlapping_setnames.has(sname)) {
        config.isoquants[sname] = result.base_analysis.isoquants[sname];
      }
    }
    for (const key of ['mzmldef', 'flags', 'inputparams', 'multicheck', 'fileparams']) {
      config[key] = result.base_analysis[key];
    }
    Object.assign(config.multifileparams, result.base_analysis.multifileparams);
    config = config;
  }
}


function removeMultifile(fparam_id, key) {
  delete(config.multifileparams[fparam_id][key]);
  let newmfp = {}
  Object.keys(config.multifileparams[fparam_id]).forEach((k, ix) => {
    newmfp[ix] = config.multifileparams[fparam_id][k]
  });
  config.multifileparams[fparam_id] = newmfp;
}

function addMultifile(fparam_id) {
  const keyints = Object.keys(config.multifileparams[fparam_id]).map(x => +x);
  const newkey = keyints.length ? Math.max(...keyints) + 1 : 0;
  config.multifileparams[fparam_id][newkey] = '';
}

function getIntextFileName(fnid, files) {
  if (files && fnid in files) {
    return files[fnid].name 
  } else {
    return '';
  }
}

function matchFractions(ds) {
  let allfrs = new Set();
  for (let fn of ds.files) {
    const match = fn.name.match(RegExp(ds.frregex));
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
  }).map(x => {return {ch: x[0], sample: x[1][0], chid: x[1][1]}});
}

function updateIsoquant() {
  // Add new set things if necessary
  if ('isobaric_quant' in wf.components || 'sampletable' in wf.components) {
    Object.values(dsets).forEach(ds => {
      const errmsg = `Sample set mixing error! Channels for datasets with setname ${ds.setname} are not identical!`;
      notif.errors[errmsg] = 0;
      if (ds.setname && !(ds.setname in config.isoquants)) {
        config.isoquants[ds.setname] = {
          chemistry: ds.details.qtypeshort,
          channels: ds.details.channels,
          samplegroups: Object.fromEntries(Object.keys(ds.details.channels).map(x => [x, ''])),
          denoms: Object.fromEntries(Object.keys(ds.details.channels).map(x => [x, false])),
          report_intensity: false,
          sweep: false,
        };
      } else if (ds.setname && ds.setname in config.isoquants) {
        const dskeys = new Set(Object.keys(ds.details.channels))
        const isokeys = Object.keys(config.isoquants[ds.setname].channels);
        if (isokeys.length !== dskeys.size) {
            notif.errors[errmsg] = 1;
        } else {
          for (const ch of isokeys) {
            if (!dskeys.has(ch)) {
              notif.errors[errmsg] = 1;
              break;
            }
            ds.details.channels[ch].map((val, ix) => {
              if (val !== config.isoquants[ds.setname].channels[ch][ix]) {
                notif.errors[errmsg] = 1;
              }
            });
          }
        }
      }
    });
    // Remove old sets from config.isoquants if necessary
    const dset_sets = new Set(Object.values(dsets).map(ds => ds.setname).filter(x => x));
    Object.keys(config.isoquants).filter(x => !(dset_sets.has(x))).forEach(x => {
      delete(config.isoquants[x])
    });
    config.isoquants = Object.assign({}, config.isoquants);  // assign so svelte notices (doesnt act on deletion)
  }
}

async function populate_analysis() {
  config.wfid = existing_analysis.wfid;
  config.wfversion_id = existing_analysis.wfversion_id;
  config.wfversion = allwfs[existing_analysis.wfid].versions.filter(x => x.id === existing_analysis.wfversion_id)[0];
  for (const key of ['analysisname', 'mzmldef', 'flags', 'inputparams', 'multicheck', 'fileparams', 'isoquants']) {
    config[key] = existing_analysis[key];
  }
  await fetchWorkflow();
  Object.assign(config.multifileparams, existing_analysis.multifileparams);
  base_analysis = existing_analysis.base_analysis || base_analysis;
  // FIXME now repopulate files with sample names if any
}


onMount(async() => {
  await fetchAllWorkflows();
  if (existing_analysis) {
    await populate_analysis();
  }
  await fetchDatasetDetails(false);
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

  <div class="box">
    <div class="title is-5">Fetch settings/files from a previous analysis</div>
    {#if wf && 'complement_analysis' in wf.components && base_analysis.selected}
    <div class="checkbox">
      {#if base_analysis.dsets_identical}
      <input type="checkbox" bind:checked={base_analysis.runFromPSM}>
      <label class="checkbox">
        Re-analyze previous analysis from PSM table, skipping identification steps
      </label>
      <a title="For output changes post-PSM table, e.g. for changes in quantification only. Any changes to fractions, input datasets, modifications etc will be ignored. For this to work you may not change set names."><i class="fa fa-question-circle"></i></a>
      {:else}
      <input type="checkbox" bind:checked={base_analysis.isComplement}>
      <label class="checkbox">
        Complement previous analysis with new or re-run sets (with replaced or extra raw data)
      </label>
      <a title="Skips parts of analysis already run, faster output"><i class="fa fa-question-circle"></i></a>
      {/if}
    </div>
    {/if}
    <DynamicSelect bind:intext={base_analysis.typedname} bind:selectval={base_analysis.selected} on:selectedvalue={e => loadBaseAnalysis()} niceName={x => x.name} fetchUrl="/analysis/baseanalysis/show/" bind:fetchedData={base_analysis.fetched} />
	</div>

  {#if 'mzmldef' in wf.components}
  <div class="title is-5">Mzml input type</div>
  <div class="field">
    <div class="select">
      <select bind:value={config.mzmldef}>
        <option value={false}>Please select one</option>
        {#each Object.keys(wf.components.mzmldef) as comp}
        <option value={comp}>{comp.split(' ').map(x => `${x[0].toUpperCase()}${x.slice(1).toLowerCase()}`).join(' ')} ({wf.components.mzmldef[comp].join(', ')})</option>
        {/each}
      </select>
    </div>
  </div>
  {/if}
  {/if}

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
				<label class="checkbox">One sample - one file (non-fractionated, non-isobaric)</label>
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
        {#if ds.changed}
        <div class="has-text-danger">
          <span>This dataset has changed files while editing  <button on:click={e => fetchDatasetDetails([ds.id])} class="button is-small">Reload dataset</button></span>
        </div>
        {/if}
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
      {#if wf}
        {#if ds.prefrac && 'mzmldef' in wf.components && config.mzmldef in wf.components.mzmldef && wf.components.mzmldef[config.mzmldef].indexOf('plate') > -1}
        <div class="field">
					<label class="label">Regex for fraction detection</label>
          <input type="text" class="input" on:change={e => matchFractions(ds)} bind:value={ds.frregex}>
				</div>
				<span>{matchedFr[ds.id]} fractions matched</span>
        {/if}
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

  {#if wf}
  {#if 'isobaric_quant' in wf.components && Object.keys(config.isoquants).length}
  <div class="box">
		<div class="title is-5">Isobaric quantification</div>
    {#each Object.entries(config.isoquants) as isoq}
    <div class="has-text-primary title is-6">Set: {isoq[0]}</div>

    {#if !('labelcheck' in wf.components)}
    {#if Object.keys(config.isoquants).length === 1 && !Object.values(isoq[1].denoms).filter(x=>x).length}
      <div class="field">
        <input type="checkbox" bind:checked={isoq[1].sweep}>
        <label class="checkbox">Use median sweeping (no predefined denominators)
          <span class="icon is-small">
            <a title="Pick median denominator per PSM, only for single-set analyses"><i class="fa fa-question-circle"></i></a>
          </span>
        </label>
      </div>
      {/if}

      {#if !isoq[1].sweep && !Object.values(isoq[1].denoms).filter(x => x).length}
      <div class="field">
        <input type="checkbox" bind:checked={isoq[1].report_intensity}>
        <label class="checkbox">Report isobaric ion intensities instead of ratios
          <span class="icon is-small">
            <a title="Reports median intensity rather than fold changes, not for use with DEqMS"><i class="fa fa-question-circle"></i></a>
          </span>
        </label>
      </div>
      {/if}
    {/if}

    <div class="columns">
      <div class="column is-three-quarters">
        <table class="table is-striped is-narrow">
          <thead>
            <tr>
            {#if !('labelcheck' in wf.components)}
              {#if !isoq[1].sweep && !isoq[1].report_intensity}
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
                LEAVE EMPTY FOR INTERNAL STANDARDS!
              </th>
            {/if}
      		  </tr>
          </thead>
          <tbody>
            {#each sortChannels(isoq[1].channels) as {ch, sample}}
            <tr>
              {#if !('labelcheck' in wf.components)}
              <td>
                {#if !isoq[1].sweep && !isoq[1].report_intensity}
                <input type="checkbox" bind:checked={isoq[1].denoms[ch]} />
                {/if}
              </td>
              {/if}
              <td>{ch}</td>
              <td>{sample}</td>
              {#if !('labelcheck' in wf.components)}
              <td>
                <input type="text" class="input" bind:value={isoq[1].samplegroups[ch]} placeholder="Sample group or empty (e.g. CTRL, TREAT)">
              </td>
              {/if}
      		  </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
    {/each}
  </div>
  {/if}

  {#if wf.multicheck.length + wf.numparams.length + wf.flags.length + wf.textparams.length}
  <div class="box">
    <div class="title is-5">Workflow parameters</div>
    {#each wf.multicheck as {nf, id, name, opts, help}}
    <div class="field">
      <label class="label">{name} 
        {#if help}
          <a title={help}><i class="fa fa-question-circle"></i></a>
        {/if}
        <code>{nf}</code></label> 
      {#each Object.entries(opts) as opt}
      <div>
        <input value={`${id}___${opt[0]}`} bind:group={config.multicheck} type="checkbox">
        <label class="checkbox">{opt[1]}</label>
      </div>
      {/each}
    </div>
    {/each}

    {#each wf.textparams as {nf, id, name, type, help}}
    <div class="field">
      <label class="label">{name} 
        {#if help}
          <a title={help}><i class="fa fa-question-circle"></i></a>
        {/if}
        <code>{nf}</code>
      </label> 
      <input type="text" class="input" bind:value={config.inputparams[id]}>
    </div>
    {/each}

    {#each wf.numparams as {nf, id, name, type, help}}
    <div class="field">
      <label class="label">{name} 
        {#if help}
          <a title={help}><i class="fa fa-question-circle"></i></a>
        {/if}
        <code>{nf}</code></label> 
      <input type="number" class="input" bind:value={config.inputparams[id]}>
    </div>
    {/each}

    <label class="label">Config flags</label>
    {#each wf.flags as {nf, id, name, help}}
    <div>
      <input value={id} bind:group={config.flags} type="checkbox">
      <label class="checkbox">{name}</label>: <code>{nf}</code> 
        {#if help}
          <a title={help}><i class="fa fa-question-circle"></i></a>
        {/if}
    </div>
    {/each}
	</div>
  {/if}


  {#if wf.multifileparams.length + wf.fileparams.length}
  <div class="box">
    <div class="title is-5">Input files</div>
    Pick previous analyses to use results as input if needed:
    <DynamicSelect bind:intext={adding_analysis.typedname} bind:selectval={adding_analysis.selected} on:selectedvalue={e => loadAnalysisResults()} niceName={x => x.name} fetchUrl="/analysis/baseanalysis/show/" bind:fetchedData={adding_analysis.fetched} />

    <div class="tags">
    {#each added_analyses_order as anaid}
      <span class="tag is-medium is-info">
        {added_results[anaid].analysisname}
        <button class="delete is-small" on:click={e => removeAnalysisResults(anaid)}></button>
      </span>
    {/each}
    </div>

    {#each wf.multifileparams as filep}
      <label class="label">{filep.name} 
          <a on:click={e => addMultifile(filep.id)} title="Add another file"><i class="fa fa-plus-square"></i></a>
          {#if filep.help}
            <a title={filep.help}><i class="fa fa-question-circle"></i></a>
          {/if}
      </label>
      {#each Object.keys(config.multifileparams[filep.id]) as mfpkey}
      <label class="label is-small">
        File nr. {mfpkey} 
        <span class="icon is-small">
          <a on:click={e => removeMultifile(filep.id, mfpkey)} title="Remove this file"><i class="fa fa-trash-alt"></i></a>
        </span>
      </label>
        <div class="field">
          {#if !filep.allow_resultfile}
          <DynamicSelect bind:selectval={config.multifileparams[filep.id][mfpkey]} niceName={x => x.name} fixedoptions={libfiles[filep.ftype]} fixedorder={libfnorder[filep.ftype]} />
          {:else}
          <DynamicSelect bind:selectval={config.multifileparams[filep.id][mfpkey]} niceName={x => x.name} fixedoptions={Object.assign(resultfiles, libfiles[filep.ftype])} fixedorder={resultfnorder.concat(libfnorder[filep.ftype])} />
          {/if}
        </div>
      {/each}
    {/each}

    {#each wf.fileparams as filep}
    <div class="field">
      <label class="label">
        {filep.name} 
        {#if filep.help}
          <a title={filep.help}><i class="fa fa-question-circle"></i></a>
        {/if}
      </label>
      {#if !filep.allow_resultfile}
      <DynamicSelect bind:selectval={config.fileparams[filep.id]} niceName={x => x.name} fixedoptions={libfiles[filep.ftype]} fixedorder={libfnorder[filep.ftype]} />
      {:else}
      <DynamicSelect bind:selectval={config.fileparams[filep.id]} niceName={x => x.name} fixedoptions={Object.assign(resultfiles, libfiles[filep.ftype])} fixedorder={resultfnorder.concat(libfnorder[filep.ftype])} />
      {/if}
    </div>
    {/each}
	</div>
  {/if}


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

  {#if runButtonActive && (!existing_analysis || existing_analysis.editable)}
  <a class="button is-primary" on:click={storeAnalysis}>Store analysis</a>
  <a class="button is-primary" on:click={runAnalysis}>Store and queue analysis</a>
  {:else if postingAnalysis}
	<a class="button is-primary is-loading">Store analysis</a>
	<a class="button is-primary is-loading">Store and queue analysis</a>
  {:else}
	<a class="button is-primary" disabled>Store analysis</a>
	<a class="button is-primary" disabled>Store and queue analysis</a>
  {/if}

  {/if} 
</div>
