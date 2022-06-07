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
    <h4 class="title is-4">{analysis.name}</h4>
    {#if analysis.errmsg}
    <div class="notification is-danger is-light"> 
      ERROR(S):
      {#each analysis.errmsg as err}
      <div>{err}</div>
      {/each}
    </div>
    {/if}

    {#if analysis.base_analysis.nfsid}
    <p><span class="has-text-weight-bold">Complementing previous run:</span> <a href={`#/analyses?ids=${analysis.base_analysis.nfsid}`}>{analysis.base_analysis.name}</a></p>
    {/if}
    <p><span class="has-text-weight-bold">Workflow version:</span> {analysis.wf.name} - {analysis.wf.update}</p>
    <p>
      <span class="has-text-weight-bold">Input data:</span> 
      {analysis.nrfiles} raw files from {analysis.nrdsets} dataset(s) analysed
      {#if analysis.base_analysis.nfsid}
      ({analysis.base_analysis.nrdsets} datasets, {analysis.base_analysis.nrfiles} files cumulatively analysed in previous run)
      {/if}
    </p>
    <p><span class="has-text-weight-bold">Quant type:</span> {analysis.quants.join(', ')}</p>
    <p><span class="has-text-weight-bold">Last lines of log  
      {#if analysis.log[0].slice(0, 16) !== 'Analysis without'}
      <a href={`analysis/log/${anaid}`} class="is-size-7" target="_blank">(full log)</a>
      {/if}
      :</span>
    </p>
    <p class="is-size-7 is-family-monospace">
    {#each analysis.log as logline}
    {logline}<br>
    {/each}
    </p>


    <div class="content">
    <p class="has-text-weight-bold">Output</p>
    {#each analysis.storage_locs as {server, path, share}}
    <div class="tags has-addons">
      <span class="tag">{server}</span>
      <span class="tag is-primary">{share} </span>
      &nbsp;{path}
    </div>
    {/each}
    {#each analysis.servedfiles as linkname}
    <div><a href="analysis/showfile/{linkname[0]}" target="_blank">{linkname[1]}</a></div>
    {/each}
    </div>

    <div class="content">
      <p class="has-text-weight-bold">Input files</p>
      {#each analysis.invocation.files as {param, multif}}
      <p>
        <code>{param}</code> 
        {#each multif as {fn, fnid, desc, parentanalysis, anid}}
        <div>
          {#if parentanalysis}
          from <a target="_blank" href={`#/analyses?ids=${anid}`}>{parentanalysis}</a> ( <a href={`#/files?ids=${fnid}`}>{fn}</a> )
          {:else}
          {desc} ( <a href={`#/files?ids=${fnid}`}>{fn}</a> )
          {/if}
        </div>
        {/each}
      </p>
      {/each}
    </div>

    <div class="content">
      <h6 class="title is-6">Other parameters</h6>
      <code>{analysis.invocation.params.join(' ')}</code>
    </div>

    <div class="content">
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
    </div>

  {/each}
</DetailBox>
