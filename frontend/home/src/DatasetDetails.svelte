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
let replace_pwiz_id = Object.fromEntries(dsetIds.map(x => [x, false]));
let refine_v_touse = Object.fromEntries(dsetIds.map(x => [x, false]));
let pwstateColors = {
  Ready: 'is-success',
  Incomplete: 'is-warning',
  Processing: 'is-danger is-light',
}

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

async function convertDset(dsid, pwiz_id) {
  const resp = await postJSON('createmzml/', {dsid: dsid, pwiz_id: pwiz_id});
  if (!resp.ok) {
    const msg = `Something went wrong trying to queue dataset mzML conversion: ${resp.error}`;
    notif.errors[msg] = 1;
    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
  } else {
    cleanFetchDetails(dsetIds);
    const msg = 'Queued dataset for mzML conversion';
    notif.messages[msg] = 1;
    setTimeout(function(msg) { notif.messages[msg] = 0 } , flashtime, msg);
  }
}

async function refineDset(dsid, refine_id) {
  const resp = await postJSON('refinemzml/', {dsid: dsid, refine_id: refine_id});
  if (!resp.ok) {
    const msg = `Something went wrong trying to queue precursor refining: ${resp.error}`;
    notif.errors[msg] = 1;
    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
  } else {
    cleanFetchDetails(dsetIds);
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

  {#if 'pwiz_versions' in dset}
  <div class="field">
    <label class="label">Conversion mzML results / pipeline version(s)</label>
    <table class="table">
      <tbody>
        {#each dset.pwiz_sets as pw}
        <tr>
          <td>
            {#if pw.state === 'Incomplete' && pw.refined}
            <button class="button is-small" on:click={e => refineDset(dsid, pw.id)}>Re-refine</button>
            {:else if pw.state === 'Incomplete'}
            <button class="button is-small" on:click={e => convertDset(dsid, pw.id)}>Re-convert</button>
            {:else if pw.refineready}
            <div class="select is-small">
              <select bind:value={refine_v_touse[dset.id]}>
                <option value="">Pick a refine version</option>
                {#each dset.refine_versions as {id, name}}
                <option value={id}>Refine {name}</option>
                {/each}
              </select>
            </div>
            <button class="button is-small" on:click={e => refineDset(dsid, refine_v_touse[dset.id])}>Refine mzML</button>
            {/if}
          </td>
          <td>
            <span class={`tag ${pwstateColors[pw.state]}`}>
              {pw.state}
            </span>
          </td>
          <td><span class="has-text-weight-bold">{pw.version}</span><span>, created {pw.created}</span></td>
          <td>
            {#if pw.refined}
            <span class="tag is-light is-warning">Refined</span>
            {/if}
          </td>
        </tr>
        {/each}
      </tbody>
    </table>
  </div>
    
  <div class="field">
    {#if Object.keys(dset.pwiz_versions).length}
    <div>Or replace with mzMLs of another version</div>
    {/if}
    <div class="select">
      <select bind:value={replace_pwiz_id[dset.id]}>
        <option value="">Pick a proteowizard version</option>
        {#each Object.entries(dset.pwiz_versions) as pwiz_v}
        <option value={pwiz_v[0]}>{pwiz_v[1]}</option>
        {/each}
      </select>
    </div>
    {#if replace_pwiz_id[dset.id]}
    <button on:click={e => convertDset(dsid, replace_pwiz_id[dset.id])} class="button">Convert!</button>
    {:else}
    <button disabled class="button">Convert!</button>
    {/if}
  </div>
  {/if}

  {/each}
</DetailBox>
