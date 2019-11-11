<script>
import { onMount } from 'svelte';
import { getJSON } from './funcJSON.js';
import { createEventDispatcher } from 'svelte';

const dispatch = createEventDispatcher();

export let selectval = '';
export let fixedoptions = {};
export let fixedorder = [];
export let options = Object.fromEntries(Object.entries(fixedoptions));
export let intext;
export let fetchUrl = false;
export let niceName = function(text) { return text; }
export let unknowninput = '__PLACEHOLDER__';
export let optorder = fixedorder.length ? fixedorder : Object.keys(options);

let selectedtext;
let placeholder = 'Filter by typing';
let typing = false;


function inputdone() {
  typing = false;
  if (selectval && selectval in options) {
    intext = niceName(options[selectval]);
  } else if (unknowninput === '__PLACEHOLDER__') {
    console.log('illegal value');
    dispatch('illegalvalue');
  } else {
    console.log('new value');
    unknowninput = intext;
    dispatch('newvalue');
  }
}

function deselect(ev) {
  ev.target.selected = false;
  intext = '';
  placeholder = selectval ? niceName(selectval) : '';
}

function selectvalue(ev) {
  selectval = options[ev.target.value].id;
  unknowninput = '';
  dispatch('selectedvalue'); 
}

function hovervalue(ev) {
  ev.target.selected = true;
  const val = options[ev.target.value];
  intext = niceName(val);
}

async function fetchOptions() {
  if (intext.length > 2 && fetchUrl) {
    options = await getJSON(`${fetchUrl}?q=${intext}`);
    optorder = Object.keys(options);
  } else if (!fetchUrl && fixedoptions) {
    options = Object.fromEntries(Object.entries(fixedoptions).filter(x => x[1].name.toLowerCase().indexOf(intext.toLowerCase()) > -1));
    const keys = Object.keys(options);
    optorder = fixedorder.length ? fixedorder.filter(x => keys.indexOf(x.toString()) > -1) : keys;
  }
}

function starttyping() {
  const keys = Object.keys(options);
  optorder = fixedorder.length ? fixedorder : keys;
  options = fixedorder.length ? fixedoptions : options;
  typing = true;
  placeholder = selectval ? niceName(selectval) : '';
  selectval = '';
  intext = '';
}
 
</script>

<div class="control has-icons-right">
  <input type="text" class="input is-narrow" placeholder={placeholder} on:keyup={fetchOptions} on:focus={starttyping} on:blur={inputdone} bind:value={intext}>
  <span class="icon is-right"><i class="fas fa-chevron-down"></i></span>

  {#if typing}
  <div class="select is-multiple">
    <select multiple>
      {#if !Object.keys(options).length}
      <option disabled>Type more or type less...</option>
      {/if}
      {#each optorder as optid} 
      <option value={optid} on:mousedown={e => selectvalue(e)} on:mouseout={e => deselect(e)} on:mouseover={e => hovervalue(e)}>{niceName(options[optid])}</option>
      {/each}
  </select>
  </div>
  {/if}
</div>

