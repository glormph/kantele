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

let optorderindex;
$: optorderindex = Object.fromEntries(optorder.map((x, ix) => [x, ix]));

let optionels = {};
let hoveropt = false;
let selectedtext;
let placeholder = 'Filter by typing';
let typing = false;
let intoselect = false;


function inputdone() {
  if (!intoselect) {
    typing = false;
    if (selectval && selectval in options) {
      intext = niceName(options[selectval]);
    } else if (unknowninput === '__PLACEHOLDER__') {
      dispatch('illegalvalue', {});
    } else {
      unknowninput = intext;
      dispatch('newvalue', {});
    }
  }
}


function selectvalue(optid) {
  intoselect = false;
  selectval = options[optid].id;
  intext = niceName(options[selectval]);
  unknowninput = '';
  dispatch('selectvalue', {});
  inputdone();
}


async function handleKeyInput(event) {
  // Takes care of key inputs, characters and backspace/delete
  if (event.keyCode === 27) {
    intoselect = false;
    inputdone();
  } else if (hoveropt && event.keyCode === 13) {
    intoselect = false;
    selectvalue(hoveropt);
  } else if (optorder.length && event.keyCode === 40) {
    if (hoveropt && optorderindex[hoveropt] + 1 <= optorder.length) {
      // else bottom line, do nothing
      hoveropt = optorder[optorderindex[hoveropt] + 1];
    } else if (!hoveropt) {
      hoveropt = optorder[0];
    }
  } else if (optorder.length && event.keyCode === 38) {
    hoveropt = hoveropt && optorderindex[hoveropt] > 0 ? optorder[optorderindex[hoveropt] - 1] : false;
  } else if (event.key.length > 1 && !(event.keyCode===8 || event.keyCode===46)) {
    return
  } else if (intext.length > 2 && fetchUrl) {
    options = await getJSON(`${fetchUrl}?q=${intext}`);
    optorder = Object.keys(options);
    typing = true;
  } else if (!fetchUrl && fixedoptions && intext) {
    options = Object.fromEntries(Object.entries(fixedoptions).filter(x => x[1].name.toLowerCase().indexOf(intext.toLowerCase()) > -1));
    const keys = Object.keys(options);
    optorder = fixedorder.length ? fixedorder.filter(x => keys.indexOf(x.toString()) > -1) : keys;
    typing = true;
  } else if (!fetchUrl && fixedoptions) {
    options = Object.fromEntries(Object.entries(fixedoptions));
    optorder = fixedorder.length ? fixedorder : Object.keys(options);
    typing = true;
  }
}

function starttyping() {
  const keys = Object.keys(options);
  optorder = fixedorder.length ? fixedorder : keys;
  options = fixedorder.length ? fixedoptions : options;
  typing = true;
  placeholder = selectval ? niceName(selectval) : '';
  selectval = '';
  //intext = '';
}
 
</script>

<div class="control has-icons-right" tabindex="0">
  <input type="text" on:blur={inputdone} class="input is-narrow" placeholder={placeholder} on:keyup={handleKeyInput} on:focus={starttyping} bind:value={intext}>
  <span class="icon is-right"><i class="fas fa-chevron-down"></i></span>

  {#if typing}
  <div class="select is-multiple">
    <select multiple on:mousedown={e => intoselect = true} >
      {#if !Object.keys(options).length}
      <option disabled>Type more or type less...</option>
      {/if}
      {#each optorder as optid} 
      <option bind:this={optionels[optid]} selected={optid===hoveropt} value={optid} on:mouseup={e => selectvalue(optid)} on:mousemove={e => hoveropt=optid}>{niceName(options[optid])}</option>
      {/each}
  </select>
  </div>
  {/if}
</div>
