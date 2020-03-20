<script>

import TableItem from './TableItem.svelte'

export let fields;
export let order;
export let trs;
export let statecolors;
export let fixedbuttons = [];
export let selected;
export let getdetails;
export let loading;

let showDetailBox = false;
let detailsLoaded = false;
let detailBoxContent = '';

function selectAll() {
}

async function showDetails(itemId) {
  showDetailBox = itemId; 
  detailsLoaded = false;
  detailBoxContent = await getdetails(itemId);
  detailsLoaded = true;
}

</script>

<style>
.box {
  position: absolute;
}
</style>

<table class="table">
  <thead>
    <tr>
      <th>
        <input type="checkbox" v-model="allSelector" v-on:click="selectAll">
      </th>
      {#each fields as field}
      <th>
      {#if field.name.slice(0, 2) === '__'}
        <span class="icon is-small">
          <i class={`fa fa-${field.name.slice(2)}`}></i>
        </span>
      {:else}
      {field.name}
      {/if}
      </th>
      {/each}
    </tr>
  </thead>
  <tbody>
    {#each order.map(x => trs[x]) as row}
    <tr>
      <td>
        <input type="checkbox" bind:group={selected} value={row.id}>
        <a v-on:click="toggleDset(ds.id)" on:mouseenter={e => showDetails(row.id)} on:mouseleave={e => showDetailBox = false}>
          <span class="has-text-info icon is-small"> <i class="fa fa-eye"></i> </span>
          {#if showDetailBox === row.id}
          <div class="box" >
            {#if !detailsLoaded}
            <i class="fa fa-spinner fa-pulse fa-2x"></i>
            {:else}
            {@html detailBoxContent}
            {/if}
          </div>
          {/if}
        </a>
        {#each fixedbuttons as button}
        <a title={button.alt} on:click={e => button.action(row.id)}>
        <span class="icon has-text-info is-small"><i class={`fa fa-${button.name.slice(2)}`}></i></span>
        </a>
        {/each}
      </td>
        {#each fields as field}
        <td>
          {#if field.links}
          {#if row[field.links].length || row[field.links] > 0}
          <a href={`${field.linkroute}${row[field.links]}`}>
            {#if field.multi}
            {#each row[field.id] as item}
            <TableItem value={item} help={field.help} icon={field.icon} fieldtype={field.type} color={statecolors[field.id]} />
            {/each}
            {:else} 
            <TableItem value={row[field.id]} help={field.help} icon={field.icon} fieldtype={field.type} color={statecolors[field.id]} />
            {/if}
          </a>
          {/if}

          {:else}
          {#if field.multi}
          {#each row[field.id] as item}
          <TableItem value={item} help={field.help} icon={field.icon} fieldtype={field.type} color={statecolors[field.id]} />
          {/each}
          {:else} 
          <TableItem value={row[field.id]} help={field.help} icon={field.icon} fieldtype={field.type} color={statecolors[field.id]} />
          {/if}
          {/if}

        </td>
        {/each}
    </tr>
    {/each}
  </tbody>
</table>

{#if loading}
<div class="has-text-centered">
  <i class="fa fa-spinner fa-pulse fa-2x"></i>
</div>
{/if}
