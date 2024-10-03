<script>

import {  createEventDispatcher } from 'svelte';

export let selected;
export let first;
export let rest;
export let keys;
export let filters;
export let toggleFromFilter

const dispatch = createEventDispatcher();
let expanded = false;
let triangles = Object.fromEntries(keys.slice(1).map(x => [x, 'caret-down']));

function toggleExpandCollapse(key) {
  if (expanded && key != expanded) {
    triangles[expanded] = 'caret-down';
    expanded = key;
    triangles[key] = 'caret-up';
  } else {
    expanded = expanded ? false : key;
    triangles[key] = expanded ? 'caret-up' : 'caret-down';
  }
}

function toggleSelect() {
  // TODO parametrize this for gene/protein-centric tables
  dispatch('togglecheck', [first[2], rest.experiments.map(x => x[0])]);
}

</script>

<tr>
  <td>
    <input type=checkbox checked={selected} on:change={toggleSelect} />
  </td>
  <td>
    <span class="has-text-link" on:click={e => toggleFromFilter(keys[0], first[2], first[1])}>
      {#if first[2] in filters[`${first[0]}_id`]}
    <icon class="icon fa fa-trash-alt" />
    {:else}
    <icon class="icon fa fa-filter" />
    {/if}
    </span>
    {first[1]}
  </td>
  {#each keys.slice(1) as k}
  <td>
    {#if rest[k].length > 1}
    <span class="has-text-link" on:click={e => toggleExpandCollapse(k)}><icon class={`icon fa fa-${triangles[k]}`} /></span>{rest[k].length} {k}
    {:else}
    <span class="has-text-link" on:click={e => toggleFromFilter(k, rest[k][0][0], rest[k][0][1])}>
      {#if rest[k][0][0] in filters[`${k}_id`]}
    <icon class="icon fa fa-trash-alt" />
    {:else}
    <icon class="icon fa fa-filter" />
    {/if}
    </span>
    {rest[k][0][1]}
    {/if}
  </td>
  {/each}
</tr>

{#if expanded}
<tr>
  <td colspan=4>
    {#each rest[expanded] as [eid, name]}
    <span class="tag is-medium is-rounded">
    <span class="has-text-link" on:click={e => toggleFromFilter(expanded, eid, name)}>
      {#if eid in filters[`${expanded}_id`]}
      <icon class="icon fa fa-trash-alt" />
      {:else}
      <icon class="icon fa fa-filter" />
      {/if}
    </span>
{name}
    </span>
    {/each}
  </td>
</tr>
{/if}
