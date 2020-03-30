<script>
import { onMount } from 'svelte';
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'
import { flashtime } from '../../util.js'
import DetailBox from './DetailBox.svelte'

export let closeWindow;
export let anaIds;

let notif = {errors: {}, messages: {}};
let analyses = {};

// If user clicks new dataset, show that instead, run when dsetIds is updated:
$: {
  cleanFetchDetails(anaIds);
}


//async function convertDset(dsid) {
//  const resp = await postJSON('createmzml/', {dsid: dsid});
//  if (!resp.ok) {
//    const msg = `Something went wrong trying to queue dataset mzML conversion: ${resp.error}`;
//    notif.errors[msg] = 1;
//    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
//  } else {
//    dsets[dsid].mzmlable = 'blocked';
//    const msg = 'Queued dataset for mzML conversion';
//    notif.messages[msg] = 1;
//    setTimeout(function(msg) { notif.messages[msg] = 0 } , flashtime, msg);
//  }
//}
//
//async function refineDset(dsid) {
//  const resp = await postJSON('refinemzml/', {'dsid': dsid});
//  if (!resp.ok) {
//    const msg = `Something went wrong trying to queue precursor refining: ${resp.error}`;
//    notif.errors[msg] = 1;
//    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
//  } else {
//    dsets[dsid].refinable = 'blocked';
//    const msg = 'Queued dataset for mzML precursor refining';
//    notif.messages[msg] = 1;
//    setTimeout(function(msg) { notif.messages[msg] = 0 } , flashtime, msg);
//  }
//}
//
//async function changeOwner(dsid, owner, op) {
//  const resp = await postJSON('datasets/save/owner/', {
//    'dataset_id': dsid, 
//    'op': op,
//    'owner': owner});
//  if (!resp.ok) {
//    const msg = `Something went wrong trying to change owner of the dataset: ${resp.error}`;
//    notif.errors[msg] = 1;
//    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
//  } else {
//    fetchDetails([dsid]);
//  }
//  owner_to_add[dsid] = false;
//}

async function fetchDetails(anaids) {
  let fetchedAna = {}
  const tasks = anaids.map(async anaId => {
    const resp = await getJSON(`/show/analysis/${anaId}`);
    if (!resp.ok) {
      const msg = `Something went wrong fetching analysis info: ${resp.error}`;
      notif.errors[msg] = 1;
      setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
    } else {
      fetchedAna[anaId] = resp;
    }
  });
  const result = await Promise.all(tasks);
  analyses = Object.assign(analyses, fetchedAna);
}

function cleanFetchDetails(anaids) {
  analyses = {};
  fetchDetails(anaids);
}

onMount(async() => {
  cleanFetchDetails(anaIds);
});

</script>

<DetailBox notif={notif} closeWindow={closeWindow}>
  {#each Object.entries(analyses) as [anaid, analysis]}

    <h5 class="title is-6">{analysis.name}</h5>
    <p><span class="has-text-weight-bold">Last lines of log  
      {#if analysis.log[0].slice(0, 16) !== 'Analysis without'}
      <a href={`analysis/log/${anaid}`} class="is-size-7" target="_blank">(full log)</a>
      {/if}
      :</span>
    </p>
    <p class="is-family-monospace">
    {#each analysis.log as logline}
    {logline}<br>
    {/each}
    </p>

    <section class="section">
    <div class="columns">
      <div class="column">
        <h6 class="title is-6">Output</h6>
        {#each analysis.servedfiles as linkname}
        <div><a href="analysis/showfile/{linkname[0]}" target="_blank">{linkname[1]}</a></div>
        {/each}
      </div>
      <div class="column">
        <h6 class="title is-6">Input data</h6>
        <p><span class="has-text-weight-bold">Workflow version:</span> {analysis.wf.update}</p>
        <p>{analysis.nrfiles} raw files from {analysis.nrdsets} dataset(s) analysed</p>
        <p><span class="has-text-weight-bold">Quant type:</span> {analysis.quants.join(', ')}</p>
      </div>
    </div>

    <h6 class="title is-6">Pipeline parameters</h6>
    {#each analysis.invocation.files as param}
    <p><code>{param[0]}</code>: {param[2]} ( {param[1]} )</p>
    {/each}
    <p>Other parameters: <code>{analysis.invocation.params.join(' ')}<code></p>

    <h6 class="title is-6">Samples:</h6> 
    {#if analysis.invocation.sampletable}
    <table class="table">
      <thead>
        <tr>
          <th>Channel</th>
          <th>Sample set</th>
          <th>Sample name</th>
          <th>Sample group</th>
        </tr>
      </thead>
      <tbody>
        {#each analysis.invocation.sampletable as sample}
        <tr>
          {#each sample as txt}
          <td>{txt}</td>
          {/each}
        </tr>
        {/each}
      </tbody>
    </table>
    {/if}
    </section >

  {/each}
</DetailBox>
