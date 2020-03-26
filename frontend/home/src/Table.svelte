<script>

import {querystring, push} from 'svelte-spa-router';
import { onMount, createEventDispatcher } from 'svelte';
import { getJSON } from '../../datasets/src/funcJSON.js'

import TableItem from './TableItem.svelte'
import { flashtime } from '../../util.js'

export let fields;
export let statecolors;
export let fixedbuttons = [];
export let selected;
export let getdetails;
export let inactive = [];
export let fetchUrl;
export let findUrl;
export let errors;
export let tab;

const dispatch = createEventDispatcher();
let items = {};
let order = [];
let findQueryString = '';
let showDetailBox = false;
let detailsLoaded = false;
let detailBoxContent = '';
let searchdeleted = false;
let loadingItems = false;
let loadingNonce;

function selectAll() {
}

function fetchItems(ids) {
	const url = ids.length ? fetchUrl + `?ids=${ids.join(',')}` : fetchUrl;
  loadItems(url);
}

function findItems(q) {
  const url = `${findUrl}?q=${q}&deleted=${searchdeleted}`;
  loadItems(url);
}

function findQuery(event) {
  if (event.keyCode === 13) {
    // Push doesnt reload the component
    const q = findQueryString.split(' ').join(',');
    push(`#/${tab.toLowerCase()}?q=${q}&deleted=${searchdeleted}`);
    findItems(q);
  }
}

async function showDetails(itemId) {
  showDetailBox = itemId; 
  detailsLoaded = false;
  detailBoxContent = await getdetails(itemId);
  detailsLoaded = true;
}

function clickSingleDetails(rowid) {
  console.log('hej');
  dispatch('detailview', {ids: [rowid]});
}

async function loadItems(url) {
  loadingItems = true;
  const localNonce = loadingNonce = new Object();
  const result = await getJSON(url);
  loadingItems = false;
  if ('error' in result) {
    const msg = `While fetching ${tab.toLowerCase()}: ${result.error}`;
    errors[msg] = 1;
    setTimeout(function(msg) { errors[msg] = 0 } , flashtime, msg);
  } else if (localNonce !== loadingNonce) {
    // Override the previous request so only the latest gets rendered on the page
    return;
  } else {
    order = [];
    items = {};
    items = result.items;
    order = result.order;
  }
}

onMount(async() => {
  let qs;
  try {
    qs = Object.fromEntries($querystring.split('&').map(x => x.split('=')));
  } catch {
    // FIXME 404 instead
    fetchItems([]);
    return;
  } 
  if ('ids' in qs) {
    fetchItems(qs.ids.split(','));
  } else if ('q' in qs) {
    searchdeleted = ('deleted' in qs) ? true : false;
    findQueryString = qs.q.split(',').join(' ');
    findItems(qs.q);
  } else {
    fetchItems([]);
  }
})
</script>

<style>
.box {
  position: absolute;
}

div.spinner {
  position: absolute;
  left: 50%;
  padding-top: 20px;
}
</style>

<div class="content is-small">
  <input type="checkbox" bind:checked={searchdeleted}>Search deleted {tab.toLowerCase()}
  <input class="input is-small" on:keyup={findQuery} bind:value={findQueryString} type="text" placeholder="Type a query and press enter to search datasets">

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

{#if loadingItems}
<div class="has-text-centered spinner">
  <i class="fa fa-spinner fa-pulse fa-2x"></i>
</div>
{/if}

  <tbody>
    {#each order.map(x => items[x]) as row}
    <tr>
      <td>
        <input type="checkbox" bind:group={selected} value={row.id}>
        <a on:click={e => clickSingleDetails(row.id)} on:mouseenter={e => showDetails(row.id)} on:mouseleave={e => showDetailBox = false}>
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
          <a href={`${field.linkroute}?ids=${row[field.links]}`}>
            {#if field.multi}
            {#each row[field.id] as item}
            <TableItem value={item} inactive={inactive.some(x=>row[x])} help={field.help} icon={field.icon} fieldtype={field.type} color={statecolors[field.id]} />
            {/each}
            {:else} 
            <TableItem value={row[field.id]} inactive={inactive.some(x=>row[x])} help={field.help} icon={field.icon} fieldtype={field.type} color={statecolors[field.id]} />
            {/if}
          </a>
          {/if}

          {:else}
          {#if field.multi}
          {#each row[field.id] as item}
          <TableItem value={item} inactive={inactive.some(x=>row[x])} help={field.help} icon={field.icon} fieldtype={field.type} color={statecolors[field.id]} />
          {/each}
          {:else} 
          <TableItem value={row[field.id]} inactive={inactive.some(x=>row[x])} help={field.help} icon={field.icon} fieldtype={field.type} color={statecolors[field.id]} />
          {/if}
          {/if}

        </td>
        {/each}
    </tr>
    {/each}
  </tbody>
</table>
</div>
