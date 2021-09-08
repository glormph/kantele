<script>
import { onMount } from 'svelte';
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'
import { flashtime } from '../../util.js'
import DetailBox from './DetailBox.svelte'

export let closeWindow;
export let projId;

let notif = {errors: {}, messages: {}};
let items = {};
let newname = false;

// If user clicks proj, show that instead, run when projIds is updated:
$: {
  cleanFetchDetails(projId);
}

async function renameProject(newname, projid) {
  const resp = await postJSON('/datasets/rename/project/', {
    newname: newname,
    projid: projid});
  if (!resp.ok) {
    const msg = `Something went wrong trying to rename the project: ${resp.error}`;
    notif.errors[msg] = 1;
    setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
  } else {
    const msg = `Queued project for renaming to ${newname}`;
    notif.messages[msg] = 1;
    setTimeout(function(msg) { notif.messages[msg] = 0 } , flashtime, msg);
    // FIXME Should fix update in table as well
  }
  
}

// This function seems general, but I'm not sure, you could put specific stuff in it
// maybe with a callback
async function fetchDetails(ids) {
  let fetched = {}
  const tasks = ids.map(async singleId => {
    const resp = await getJSON(`/show/project/${singleId}`);
    if (!resp.ok) {
      const msg = `Something went wrong fetching project info: ${resp.error}`;
      notif.errors[msg] = 1;
      setTimeout(function(msg) { notif.errors[msg] = 0 } , flashtime, msg);
    } else {
      fetched[singleId] = resp;
      newname = resp.name;
    }
  });
  const result = await Promise.all(tasks);
  items = Object.assign(items, fetched);
}

function cleanFetchDetails(ids) {
  items = {};
  fetchDetails(ids);
}

onMount(async() => {
  cleanFetchDetails(projId);
});

</script>

<DetailBox notif={notif} closeWindow={closeWindow}>
  {#each Object.entries(items) as [projid, proj]}
  <p><span class="has-text-weight-bold">Name:</span>{proj.name}</p>
  <p><span class="has-text-weight-bold">Type:</span>{proj.type}</p>
  <p><span class="has-text-weight-bold">Registered:</span>{proj.regdate}</p>
  <p><span class="has-text-weight-bold">Owners:</span>{proj.owners.join(', ')}</p>
  <p><span class="has-text-weight-bold"># datasets:</span>{proj.nrdsets}</p>
  <p><span class="has-text-weight-bold">Stored amount:</span>{proj.stored_total_xbytes}</p>
  <p><span class="has-text-weight-bold">Instruments used:</span>{proj.instruments.join(', ')}</p>

  <hr>
  

  <div class="field is-grouped">
    <p class="control is-expanded">
      <input class="input is-small" bind:value={newname} type="text"> 
    </p>
    <p class="control">
      <a on:click={renameProject(newname, projid)} class="button is-small is-primary">Rename project</a>
    </p>
  </div>
  {/each}
</DetailBox>
