<script>

import { postJSON } from '../../datasets/src/funcJSON.js'
import DynamicSelect from '../../datasets/src/DynamicSelect.svelte';

// pre-existing variables:
// qc_instruments = {id: name}
  let qc_reruns = Object.fromEntries(
      Object.keys(instruments)
      .map(k => [k, false])
      );
  let rerunAllInstruments = false;
  let rerunNumberDays = 0;
  let rerunFromDate = 'today';
  let showConfirm = false;
  let errorMsg = '';
  let serverMsg = '';

  let selectedSingle = false;

  let ignoreObsolete = false;
  let retrieveBackups = false;


  function getRerunFromDate() {
      showConfirm = false;
      if (!rerunNumberDays) {
        rerunFromDate = 'today';
      } else if (rerunNumberDays === 1) {
        rerunFromDate = 'yesterday';
      } else {
        const today = new Date();
        today.setDate(today.getDate() - rerunNumberDays);
        rerunFromDate = today.toLocaleDateString();
      }
    }


  function toggleRerunAll() {
      rerunAllInstruments = rerunAllInstruments === false;
      Object.keys(qc_reruns)
        .forEach(k => { qc_reruns[k] = rerunAllInstruments;
          });
    }

  function checkRerun() {
    postRerun(false);
  }

  function confirmRerun() {
    postRerun(true);
  }

  async function runSingleFile() {
    errorMsg = '';
    serverMsg = '';
    const resp = await postJSON('/manage/qc/rerunsingle/', {sfid: selectedSingle});
    if (resp.state === 'ok') {
      serverMsg = resp.msg;
    } else if (resp.state === 'error') {
      errorMsg = resp.msg;
    }
  }

  async function postRerun(confirm) {
      errorMsg = '';
      serverMsg = '';
      const rerun_ids = Object.entries(qc_reruns)
        .filter(([k,v]) => v)
        .map(([k,v]) => k);
      const data = {days: rerunNumberDays, instruments: rerun_ids, confirm: confirm,
          ignore_obsolete: ignoreObsolete, retrieve_archive: retrieveBackups,
        };
      const resp = await postJSON('/manage/qc/rerunmany/', data);
      if (resp.state === 'confirm') {
        showConfirm = true;
        serverMsg = resp.msg;
      } else if (resp.state === 'error') {
        errorMsg = resp.msg;
      } else {
        showConfirm = false;
        serverMsg = resp.msg;
        ignoreObsolete = false;
        retrieveBackups = false;
      }
    }

</script>

<div class="columns">
  <div class="column">
    <div class="box has-background-link-light">
      <h4 class="title is-4">QC reruns</h4>
      <h5 class="title is-5">Run a batch of files with latest QC workflow</h5>
      <h5 class="subtitle is-5">Excludes deleted </h5>
      <div class="columns">
        <div class="column">
          <div class="field">
            <label class="checkbox">
              <input on:click={toggleRerunAll} checked={rerunAllInstruments} type="checkbox"> All instruments
            </label>
          </div>
          {#each Object.entries(instruments) as [id, name]}
          <div class="field">
            <label class="checkbox">
              <input on:click={e => showConfirm = false} bind:checked={qc_reruns[id]} type="checkbox"> {name}
            </label>
          </div>
          {/each}
        </div>
        <div class="column">
          <div class="field">
            <label class="label">How many days ago to rerun from</label>
            <input type="number" class="input" on:change={getRerunFromDate} bind:value={rerunNumberDays} />
            Rerun from {rerunFromDate}
          </div>
          {#if Object.entries(qc_reruns).filter(([k,v]) => v).length}
          <button on:click={checkRerun} class="button">Check reruns</button>
          {:else}
          <button on:click={checkRerun} class="button" disabled>Check reruns</button>
          {/if}
          {#if showConfirm}
          <button on:click={confirmRerun} class="button">Confirm</button>
          {:else}
          <button on:click={confirmRerun} class="button" disabled>Confirm</button>
          {/if}
          <div class="field mt-4">
            <label class="checkbox">
              <input checked={ignoreObsolete} type="checkbox"> Ignore obsolete warning
            </label>
          </div>
          <div class="field mt-4">
            <label class="checkbox">
              <input checked={retrieveBackups} type="checkbox"> Retrieve archived files from backup 
            </label>
          </div>

        </div>
      </div>
      <h5 class="title is-5">Or select a single run</h5>
      <DynamicSelect bind:selectval={selectedSingle} on:selectedvalue={e => console.log('hsaj')} niceName={x => x.name} fetchUrl="/manage/qc/searchfiles/" placeholder="instrument name, date" />
      {#if selectedSingle}
      <button on:click={runSingleFile} class="button">Run</button>
      {:else}
      <button class="button" disabled>Run</button>
      {/if}

      <p class="has-text-link">{serverMsg}</p>
      <p class="has-text-danger">{errorMsg}</p>
    </div>
  </div>
  <div class="column">
    <div class="box has-background-link-light">
      <h5 class="title is-5">Queues</h5>
      TBA
    </div>
  </div>
</div>
