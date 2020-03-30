<script>
import { onMount } from 'svelte';
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'
import { flashtime } from '../../util.js'
import DetailBox from './DetailBox.svelte'

export let closeWindow;
export let dsetIds;

let notif = {errors: {}, messages: {}};
let dsets = {};
let owner_to_add = Object.fromEntries(dsetIds.map(x => [x, false]));

// If user clicks new dataset, show that instead, run when dsetIds is updated:
$: {
  cleanFetchDetails(dsetIds);
}

function new_owners(allowners, oldowners) {
  const difference = Object.keys(allowners).concat(Object.keys(oldowners)).reduce(function(r, cur) {
    if (!r.delete(cur)) {
      r.add(cur);
    } return r}, new Set());
  return Array.from(difference);
}

async function convertDset(dsid) {
  const resp = await postJSON('createmzml/', {dsid: dsid});
  if (!resp.ok) {
    const msg = `Something went wrong trying to queue dataset mzML conversion: ${resp.error}`;
    notif.errors[msg] = 1;
    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
  } else {
    dsets[dsid].mzmlable = 'blocked';
    const msg = 'Queued dataset for mzML conversion';
    notif.messages[msg] = 1;
    setTimeout(function(msg) { notif.messages[msg] = 0 } , flashtime, msg);
  }
}

async function refineDset(dsid) {
  const resp = await postJSON('refinemzml/', {'dsid': dsid});
  if (!resp.ok) {
    const msg = `Something went wrong trying to queue precursor refining: ${resp.error}`;
    notif.errors[msg] = 1;
    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
  } else {
    dsets[dsid].refinable = 'blocked';
    const msg = 'Queued dataset for mzML precursor refining';
    notif.messages[msg] = 1;
    setTimeout(function(msg) { notif.messages[msg] = 0 } , flashtime, msg);
  }
}

async function changeOwner(dsid, owner, op) {
  const resp = await postJSON('datasets/save/owner/', {
    'dataset_id': dsid, 
    'op': op,
    'owner': owner});
  if (!resp.ok) {
    const msg = `Something went wrong trying to change owner of the dataset: ${resp.error}`;
    notif.errors[msg] = 1;
    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
  } else {
    fetchDetails([dsid]);
  }
  owner_to_add[dsid] = false;
}

async function fetchDetails(dsetids) {
  let fetchedDsets = {}
  const tasks = dsetids.map(async dsetId => {
    const resp = await getJSON(`/show/dataset/${dsetId}`);
    if (!resp.ok) {
      const msg = `Something went wrong fetching dataset info: ${resp.error}`;
      notif.errors[msg] = 1;
      setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
    } else {
      fetchedDsets[dsetId] = resp;
    }
  });
  const result = await Promise.all(tasks);
  dsets = Object.assign(dsets, fetchedDsets);
}

function cleanFetchDetails(dsetids) {
  dsets = {};
  fetchDetails(dsetids);
}

onMount(async() => {
  cleanFetchDetails(dsetIds);
});

</script>

<DetailBox notif={notif} closeWindow={closeWindow}>
  {#each Object.entries(dsets) as [dsid, dset]}
  <p><span class="has-text-weight-bold">Storage location:</span> {dset.storage_loc}</p>
  <hr>
  <div class="columns">
    <div class="column">

      <div class="field">
        {#each Object.entries(dset.nrstoredfiles) as fn}
        <div>{fn[1]} stored files of type {fn[0]}</div>
        {/each}
      </div>

      {#if dset.mzmlable}
      <div class="field">
        <label class="label">
          Convert to mzml using version: 
        </label>
        <div class="control">
          {#if dset.mzmlable == 'ready'}
          <div class="select">
            <select bind:value={dset.previous_or_latest_pwiz}>
              {#each dset.pwiz_versions as pwiz_v}
              <option >{pwiz_v}</option>
              {/each}
            </select>
          </div>
          <button on:click={e => convertDset(dsid)} class="button">Convert!</button>
          {:else if dset.mzmlable == 'blocked'}
          <button disabled class="button">Convert job queued</button>
          {/if}
        </div>
      </div>
      {/if}

      {#if dset.refinable}
      <div class="field">
        <label class="label">Refine precursor data</label>
        <label class="label is-small">Adjust prec.mass in case of MS drift (visible in QC)</label>
        <div class="control">
          <div class="select">
            <select bind:value={dset.previous_or_latest_pwiz}>
              {#each dset.refine_versions as refine_v}
              <option >{refine_v}</option>
              {/each}
            </select>
          </div>
          {#if ['ready', 'partly'].indexOf(dset.refinable) > -1}
          <button on:click={e => refineDset(dsid)} class="button">Start refinery</button>
          {:else if dset.refinable == 'blocked'}
          <button disabled class="button">Refinery job queued</button>
          {/if}
        </div>
      </div>
      {/if}

    </div>

    <div class="column">

      <div class="has-text-weight-bold">Owners</div>
      <div class="field is-grouped is-grouped-multiline">
        {#each Object.entries(dset.owners) as [usrid, owner]}
        <div class="control">
          <div class="tags has-addons">
            <span class="tag is-light">{owner}</span>
            <a class="tag is-info is-delete" on:click={e => changeOwner(dsid, usrid, 'del')}></a>
          </div>
        </div>
        {/each}
      </div>
      <div class="field">
        <div class="control">
          <div class="select">
            <select bind:value={owner_to_add[dsid]} on:change={e => changeOwner(dsid, owner_to_add[dsid], 'add')}>
              <option disabled value={false}>Add an owner</option>
              {#each new_owners(dset.allowners, dset.owners) as newusrid}
              <option value={newusrid}>{dset.allowners[newusrid]}</option>
              {/each}
            </select>
          </div>
        </div>
      </div>

    </div>
    <div class="column">

      {#if dset.qtype}
      <div><span class="has-text-weight-bold">Quant type</span> {dset.qtype.name}</div>
      {/if}

      <div class="has-text-weight-bold">Instrument(s)</div>
      <div class="field is-grouped is-grouped-multiline">
        {#each dset.instruments as instr}
        <div class="control">
          <div class="tags">
            <span class="tag is-light">{instr}</span>
          </div>
        </div>
        {/each}
      </div>

    </div>
  </div>

  {/each}
</DetailBox>
