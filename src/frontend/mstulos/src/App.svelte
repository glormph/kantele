<script>

import { onMount } from 'svelte';
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js';
//import NestedLinePlot from './NestedLinePlot.svelte';
import DynamicSelect from '../../datasets/src/DynamicSelect.svelte';
import Tablerow from './Tablerow.svelte';
import { schemeSet1 } from 'd3-scale-chromatic';

/*
let searchresults = {};
let searchresultorder = []
let expresultorder = [];
let expresults = {};
let query;
let selected_peps = new Set();
let selected_exps = new Set();

let plots = {
  pepfdr: '',
  pepquant: '',
};
//let data = {
//  pepfdr: [],
//  pepquant: [],
//};
let dls = {
  pepfdr: [],
  pepquant: [],
};
let series = {};
*/


/*
async function searchQ() {
  searchresults = {};
  searchresultorder = [];
  const resp = await getJSON(`find/?q=${query}`);
  resp.results.map(x => ({selected: false, ...x})).forEach(x => {
    searchresults[x.id] = x;
    searchresultorder.push(x.id);
  });
}

function toggleResults(srid) {
  if (!searchresults[srid].selected) {
    searchresults[srid].selected = true;
    searchresults[srid].experiments.forEach(x => {
      if (!(x.id in expresults)) {
        expresults[x.id] = x;
        expresultorder.push(x.id);
      }
    });
    selected_peps.add(srid);
    addSearchedItemToPlots(searchresults[srid].id, searchresults[srid].type);
    // add to plots
  } else {
    searchresults[srid].selected = false;
    selected_peps.delete(srid)
    removeItemFromPlots(srid);
  }
}

function toggleExperiment(expid) {
  if (!expresults[expid].selected) {
    expresults[expid].selected = true;
    selected_exps.add(expid);
    addExpToPlots(expid);
  } else {
    expresults[expid].selected = false;
    selected_exps.delete(expid);
    removeExpFromPlots(expid);
  }
}

function replot() {
  console.log(dls);
  ['pepfdr'].forEach(k => {
  //['pepfdr', 'pepquant'].forEach(k => {
    data[k] = Object.entries(dls[k]).map(([sam, peps]) => ({sam: sam, 
    ...Object.fromEntries(Object.entries(peps).map(([pid, nameval]) => [nameval[0], nameval[1]])) }));
    series[k] = new Set(data[k].map(d => Object.keys(d)).flat());
  // Timeout to let series propagate to the plot, for some reason it remains undefined in the plot component otherwise
    setTimeout(() => {
      plots[k].plot();
    }, 0);
  });
}

async function addExpToPlots(eid) {
  if (selected_peps.size) {
    ['pepfdr', 'pepquant'].forEach(async k => {
      const resp = await postJSON('data/', {type: 'peptide', ids: Array.from(selected_peps), experiments: [eid]});
      Object.entries(resp[k]).forEach(([exp, sampeps]) => {
        if (exp in dls[k]) {
          Object.entries(sampeps).forEach(([sam, peps]) => {
            if (sam in dls[k][exp]) {
              dls[k][exp][sam] = {...dls[k][exp][sam], ...peps};
            } else {
              dls[k][exp][sam] = peps;
            }
          });
        } else {
          dls[k][exp] = sampeps;
          // dls[k][sam] = {...dls[k][sam], ...resp[k][sam]};
        //} else {
         // dls[k][sam] = resp[k][sam];
        }
      });
    });
    replot();
  }
}


async function addSearchedItemToPlots(sid, stype) {
  if (selected_exps.size) {
    //['pepfdr', 'pepquant'].forEach(async k => {
    ['pepquant'].forEach(async k => {
      const resp = await postJSON('data/', {type: stype, ids: [sid], experiments: Array.from(selected_exps)});
      // [{featid: 2, expid: 3, val: 0.03, sam: setA}]
      Object.keys(resp[k]).forEach(point => {
        if (sam in dls[k]) {
          dls[k][sam] = {...dls[k][sam], ...resp[k][sam]};
        } else {
          dls[k][sam] = resp[k][sam];
        }
      });
    });
    replot();
//    // probably make plot-only-function of this:
//    data.pepfdr = Object.entries(data.pepfdr_dl).map(([sam, peps]) => ({sam: sam, ...peps}));
//    console.log(data.pepfdr);
//    series.pepfdr = new Set(data.pepfdr.map(d => Object.keys(d)).flat());
//    // Timeout to let series propagate to the plot, for some reason it remains undefined in the plot component otherwise
//    setTimeout(() => {
//      plots.pepfdr.plot();
//    }, 0);
  }
}

function removeItemFromPlots(iid) {
  ['pepfdr', 'pepquant'].forEach(k => {
    delete(dls[k][iid]);
  });
  selected_peps.size && selected_exps.size ? replot() : false;
}

function removeExpFromPlots() {
  Object.keys(data).forEach(k => {
    
  });
  selected_peps.size && selected_exps.size ? replot() : false;
}


*/

//        q = {'pep_ids': q[0], 
//                'protein_ids': q[1],
//                'gene_ids': q[2], 
//                'experiment_ids': q[3],
//                'sequences': q[4],
//                'protein_names': q[5],
//                'gene_names': q[6],
//                'experiment_names': q[7],
//                'aggr': q[8],
//                }

const keys = ['peptides', 'proteins', 'genes', 'experiments'];
const idfilterkeys = keys.map(x => `${x}_id`);
const textfilterkeys = keys.map(x => `${x}_text`);
//const filterkeys = idfilterkeys.concat(textfilterkeys);

let idlookups = Object.fromEntries(keys.map(x => [x, {}]));

let filters  = Object.fromEntries(textfilterkeys.concat(idfilterkeys).map(x => [x, new Set()]));
filters.expand = Object.fromEntries(keys.slice(1).map(x => [x, 0]));

function test() {
  console.log(filters.expand);
  let ppge = idfilterkeys.map(x => Array.from(filters[x])).concat(textfilterkeys.map(x => filters[x]))
  ppge = ppge.concat(keys.slice(1).map(x => filters.expand[x]));
    //(push(Array.from(filters.expand));
  const b64filter = btoa(JSON.stringify(ppge));
  location.search = `q=${b64filter}`;
}


onMount(async() => {
  const idfilters = Object.fromEntries(idfilterkeys.map(x => [x, new Set(prefilters[x])]));;
  const textfilters = Object.fromEntries(textfilterkeys.map(x => [x, prefilters[x]]));;
  filters = Object.assign(idfilters, textfilters, {expand: prefilters.expand});
  idlookups = Object.fromEntries(keys.map(x => [x, {}]));
  //filters.expand = filters.expand;
});

/* FIXME Id lookups for filters shouldn ot be sent to the server, but they should be sent to the client on
page refresh to keep the names
*/
</script>

<style>
</style>

<h2 class="title is-2">MSTulos </h2>

<div class="tile is-ancestor">
  <div class="tile is-parent is-2">
    <article class="tile is-child notification is-info is-light">
      Selected peptides:
      - Show PSM table
      - Plot data
    </article>
  </div>
  <div class="tile is-parent">
    <article class="tile is-child notification is-success is-light">
      <div class="tile is-parent is-vertical">
        <div class="tile is-child">
          <h3 class="title is-5">Filtering</h3>
          Filters are applied as such:
          any peptide is shown matching a combination of ALL of the text matches :
          e.g. pep-sequence AND (protein1 OR protein2) AND (experiment1 OR experiment2)
          Clicking on the filter funnel icon further narrows down the search
          to ONLY matching peptides matching all of the ID filters, e.g. the 
          above AND only matching geneA
          First prepare your filtering criteria, then click the filter button.
        </div>
        <div class="tile is-child">
          <div class="columns"> 
            <div class="column">
              {#each keys.slice(1) as k}
              <div>
                <input bind:checked={filters.expand[k]} type="checkbox">Expand {k}
              </div>
              {/each}

            </div>
            <div class="column">
              <div>
                <label class="label">Peptides (exact match)</label>
                <div class="field has-addons">
                  <div class="control">
                    <textarea bind:value={filters.peptides_text}></textarea>
                  </div>
                </div>
              </div>
              <div>
                <label class="label">Peptides (ids)</label>
                {#if !filters.peptides_id.size}
                -
                {/if}
                <div class="field is-grouped is-grouped-multiline">
                  {#each Array.from(filters.peptides_id) as pepid}
                  <div class="control">
                    <span class="tags has-addons">
                      <span class="tag">{pepid}</span>
                      <span class="tag is-primary">{idlookups.peptides[pepid]}
                        <button class="delete"/>
                      </span>
                    </span>
                  </div>
                  {/each}
                </div>
              </div>
            </div>
            <div class="column">
              <label class="label">Proteins (exact, case-insensitive)</label>
              <div class="field has-addons">
                <div class="control">
                  <textarea bind:value={filters.proteins_text}></textarea>
                </div>
              </div>
              <div>
                <label class="label">Proteins (ids)</label>
                {#if !filters.proteins_id.size}
                -
                {/if}
                <div class="field is-grouped is-grouped-multiline">
                  {#each Array.from(filters.proteins_id) as pid}
                  <div class="control">
                    <span class="tags has-addons">
                      <span class="tag">{pid}</span>
                      <span class="tag is-primary">{idlookups.proteins[pid]}
                        <button class="delete"/>
                      </span>
                    </span>
                  </div>
                  {/each}
                </div>
              </div>
            </div>
            <div class="column">
              <label class="label">Genes (exact, case-insensitive)</label>
              <div class="field has-addons">
                <div class="control">
                  <textarea bind:value={filters.genes_text}></textarea>
                </div>
              </div>
              <div>
                <label class="label">Genes (ids)</label>
                {#if !filters.genes_id.size}
                -
                {/if}
                <div class="field is-grouped is-grouped-multiline">
                  {#each Array.from(filters.genes_id) as gid}
                  <div class="control">
                    <span class="tags has-addons">
                      <span class="tag">{gid}</span>
                      <span class="tag is-primary">{idlookups.genes[gid]}
                        <button class="delete"/>
                      </span>
                    </span>
                  </div>
                  {/each}
                </div>
              </div>
            </div>
            <div class="column">
              <label class="label">Experiments (partial match)</label>
              <div class="field has-addons">
                <div class="control">
                  <textarea bind:value={filters.experiments_text}></textarea>
                </div>
              </div>
              <div>
                <label class="label">Experiments(ids)</label>
                {#if !filters.experiments_id.size}
                -
                {/if}
                <div class="field is-grouped is-grouped-multiline">
                  {#each Array.from(filters.experiments_id) as eid}
                  <div class="control">
                    <span class="tags has-addons">
                      <span class="tag">{eid}</span>
                      <span class="tag is-primary">{idlookups.experiments[eid]}
                        <button class="delete"/>
                      </span>
                    </span>
                  </div>
                  {/each}
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="tile is-child">
          <button class="button" on:click={test}>Apply filter</button>
        </div>
      </div>
    </article>
  </div>
</div>

<table class="table is-striped is-fullwidth">
  <thead>
    <th></th>
    {#each keys as th}
    <th>{th[0].toUpperCase()}{th.slice(1)}</th>
    {/each}
  </thead>
  <tbody>
    {#each data as row}
    <Tablerow first={['peptides', row.seq, row.id]} rest={row} keys={keys} bind:filters={filters} bind:idlookups={idlookups} />
    {/each}
  </tbody>
</table>

