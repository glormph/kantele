<script>
import Tablefield from './Tablefield.svelte';

export let first;
export let rest;
export let keys;
export let filters;
export let idlookups;

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

function toggleFromFilter(key, itemid, itemname) {
  const idkey = `${key}_id`;
  if (!filters[idkey].delete(itemid)) {
    filters[idkey].add(itemid);
    idlookups[key][itemid] = itemname;
  } else {
    delete(idlookups[key][itemid]);
  }
  filters[idkey] = filters[idkey];
}

</script>

<tr>
  <td>
    <span class="has-text-link" on:click={e => toggleFromFilter(keys[0], first[2], first[1])}>
      {#if filters[`${first[0]}_id`].has(first[2])}
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
      {#if filters[`${k}_id`].has(rest[k][0][0])}
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
      {#if filters[`${expanded}_id`].has(eid)}
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
