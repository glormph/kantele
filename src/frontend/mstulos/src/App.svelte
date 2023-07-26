<script>

import { onMount } from 'svelte';
import Tablerow from './Tablerow.svelte';

const keys = ['peptides', 'proteins', 'genes', 'experiments'];
const idfilterkeys = keys.map(x => `${x}_id`);
const textfilterkeys = keys.map(x => `${x}_text`);
const exacttextfilterkeys = keys.map(x => `${x}_text_exact`);

let selectedrows = {};
let filters;

function clearFilters() {
  filters = Object.fromEntries(
    textfilterkeys.map(x => [x, ''])
    .concat(idfilterkeys.map(x => [x, {}]))
    .concat(exacttextfilterkeys.map(x => [x, 0]))
  );
  filters.pep_excludes = '';
  filters.expand = Object.fromEntries(keys.slice(1).map(x => [x, 0]));
}
clearFilters();

function filterItems() {
  let ppge = idfilterkeys
    .map(x => Object.entries(filters[x]))
    .concat(textfilterkeys.map(x => filters[x]))
    .concat(exacttextfilterkeys.map(x => filters[x]));
  ppge = ppge.concat(keys.slice(1).map(x => filters.expand[x])).concat(filters.pep_excludes);
  const b64filter = btoa(JSON.stringify(ppge));
  location.search = `q=${b64filter}`;
}

function toggleFromFilter(key, itemid, itemname) {
  const idkey = `${key}_id`;
  if (itemid in filters[idkey]) {
    delete(filters[idkey][itemid]);
  } else {
    filters[idkey][itemid] = itemname;
  }
  // refresh for svelte to update elements
  filters[idkey] = filters[idkey];
}

function selectAll() {
  if (data.length === Object.keys(selectedrows).length) {
    selectedrows = {};
  } else {
    data.forEach(x => selectedrows[x.id] = x.experiments.map(x => x[0]))
  }
}

function toggleSelectRow(event) {
  const [row, exps] = event.detail;
  if (row in selectedrows) {
    delete(selectedrows[row]);
  } else {
    selectedrows[row] = exps;
  }
}

function openPSMTable() {
  const b64pepexps = btoa(JSON.stringify(selectedrows));
  open(`/mstulos/psms/?q=${b64pepexps}`, '_blank');
}

function openPeptideTable() {
  const b64pepexps = btoa(JSON.stringify(selectedrows));
  open(`/mstulos/peptides/?q=${b64pepexps}`, '_blank');
}


onMount(async() => {
  const idfilters = Object.fromEntries(idfilterkeys.map(x => [x, Object.fromEntries(prefilters[x])]));;
  const textfilters = Object.fromEntries(textfilterkeys.map(x => [x, prefilters[x]]));;
  const exactfilters = Object.fromEntries(exacttextfilterkeys.map(x => [x, prefilters[x]]));
  filters = Object.assign(idfilters, textfilters, exactfilters, {expand: prefilters.expand, pep_excludes: prefilters.pep_excludes});
});
</script>


<div class="tile is-ancestor">
  <div class="tile is-parent is-2">
    <article class="tile is-child notification is-info is-light">
      <h5 class="title is-5">Selected peptides</h5>
      <button on:click={openPSMTable} class="button">Show PSMs</button>
      <button on:click={openPeptideTable} class="button">Show peptides</button>
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
          Multiple filters in the same box are separated by newlines.
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
                <label class="label">Peptides</label>
                <input type=checkbox bind:checked={filters.peptides_text_exact}> Exact match (faster)
                <div class="field has-addons">
                  <div class="control">
                    <textarea bind:value={filters.peptides_text}></textarea>
                  </div>
                </div>
              <div>
                <label class="label">Peptides (ids)</label>
                {#if !Object.keys(filters.peptides_id).length}
                -
                {/if}
                <div class="field is-grouped is-grouped-multiline">
                  {#each Object.entries(filters.peptides_id) as [pepid, pepseq]}
                  <div class="control">
                    <span class="tags has-addons">
                      <span class="tag">{pepid}</span>
                      <span class="tag is-primary">{pepseq}
                        <button on:click={e => toggleFromFilter('peptides', pepid, '')} class="delete"/>
                      </span>
                    </span>
                  </div>
                  {/each}
                </div>
              </div>
            </div>
            <div class="column">
              <label class="label">Proteins</label>
              <input type=checkbox bind:checked={filters.proteins_text_exact}> Exact match (faster)
              <div class="field has-addons">
                <div class="control">
                  <textarea bind:value={filters.proteins_text}></textarea>
                </div>
              </div>
              <div>
                <label class="label">Proteins (ids)</label>
                {#if !Object.keys(filters.proteins_id).length}
                -
                {/if}
                <div class="field is-grouped is-grouped-multiline">
                  {#each Object.entries(filters.proteins_id) as [pid, pname]}
                  <div class="control">
                    <span class="tags has-addons">
                      <span class="tag">{pid}</span>
                      <span class="tag is-primary">{pname}
                        <button on:click={e => toggleFromFilter('proteins', pid, '')} class="delete"/>
                      </span>
                    </span>
                  </div>
                  {/each}
                </div>
              </div>
            </div>
            <div class="column">
              <label class="label">Genes</label>
              <input type=checkbox bind:checked={filters.genes_text_exact}> Exact match (faster)
              <div class="field has-addons">
                <div class="control">
                  <textarea bind:value={filters.genes_text}></textarea>
                </div>
              </div>
              <div>
                <label class="label">Genes</label>
                {#if !Object.keys(filters.genes_id).length}
                -
                {/if}
                <div class="field is-grouped is-grouped-multiline">
                  {#each Object.entries(filters.genes_id) as [gid, gn]}
                  <div class="control">
                    <span class="tags has-addons">
                      <span class="tag">{gid}</span>
                      <span class="tag is-primary">{gn}
                        <button on:click={e => toggleFromFilter('genes', gid, '')} class="delete"/>
                      </span>
                    </span>
                  </div>
                  {/each}
                </div>
              </div>
            </div>
            <div class="column">
              <label class="label">Experiments</label>
              <input type=checkbox bind:checked={filters.experiments_text_exact}> Exact match (faster)
              <div class="field has-addons">
                <div class="control">
                  <textarea bind:value={filters.experiments_text}></textarea>
                </div>
              </div>
              <div>
                <label class="label">Experiments(ids)</label>
                {#if !Object.keys(filters.experiments_id).length}
                -
                {/if}
                <div class="field is-grouped is-grouped-multiline">
                  {#each Object.entries(filters.experiments_id) as [eid, ename]}
                  <div class="control">
                    <span class="tags has-addons">
                      <span class="tag">{eid}</span>
                      <span class="tag is-primary">{ename}
                        <button on:click={e => toggleFromFilter('experiments', eid, '')} class="delete"/>
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
          <label class="label">Exclude sequences containing:</label>
          Use sequences or write e.g. <code>intC</code> <br>for internal Cysteine
          <div class="field has-addons">
            <div class="control">
              <textarea bind:value={filters.pep_excludes}></textarea>
            </div>
          </div>
        </div>
        <div class="tile is-child">
          <button class="button" on:click={filterItems}>Apply filter</button>
          <button class="button" on:click={clearFilters}>Clear filters</button>
        </div>
      </div>
    </article>
  </div>
</div>

<table class="table is-striped is-fullwidth">
  <thead>
    <th><input type=checkbox on:change={selectAll} /></th>
    {#each keys as th}
    <th>{th[0].toUpperCase()}{th.slice(1)}</th>
    {/each}
  </thead>
  <tbody>
    {#each data as row}
    <Tablerow selected={selectedrows[row.id]} first={['peptides', row.seq, row.id]} rest={row} keys={keys} on:togglecheck={toggleSelectRow} toggleFromFilter={toggleFromFilter} bind:filters={filters} />
    {/each}
  </tbody>
</table>

{#if !data.length}
<div class="has-text-centered">No data found for this query</div>
{/if}

