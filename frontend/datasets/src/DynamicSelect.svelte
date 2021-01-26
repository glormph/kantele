<script>
import { getJSON } from './funcJSON.js';
import { createEventDispatcher } from 'svelte';

const dispatch = createEventDispatcher();

export let selectval = '';
export let fixedoptions = {};
export let fixedorder = [];
export let intext;
export let fetchUrl = false;
export let fetchedData;
export let niceName = function(text) { return text; }
export let unknowninput = '__ILLEGAL_PLACEHOLDER__';

let options;
$: options = Object.fromEntries(Object.entries(fixedoptions));
let optorder = [];
let optorderindex;
$: optorderindex = Object.fromEntries(optorder.map((x, ix) => [x, ix]));

let hoveropt = false;
let selectedtext;
let placeholder = 'Filter by typing';
let typing = false;
let mouseSelect = false;


function inputdone() {
  if (!mouseSelect) {
    typing = false;
    if (selectval && selectval in options) {
      intext = niceName(options[selectval]);
    } else if (unknowninput === '__ILLEGAL_PLACEHOLDER__') {
      console.log('illegal value dectected');
      dispatch('illegalvalue', {});
    } else {
      unknowninput = intext;
      dispatch('newvalue', {});
    }
  }
}


function selectvalue(optid) {
  mouseSelect = false;
  selectval = options[optid].id;
  intext = niceName(options[selectval]);
  if (unknowninput !== '__ILLEGAL_PLACEHOLDER__') {
    unknowninput = '';
  }
  dispatch('selectedvalue', {});
  inputdone();
}


async function handleKeyInput(event) {
  // Takes care of key inputs, characters and backspace/delete
  if (event.keyCode === 27) {
    // escape
    mouseSelect = false;
    inputdone();
  } else if (hoveropt && (event.keyCode === 13 || event.keyCode === 9)) {
    // return || tab pressed in hover
    mouseSelect = false;
    selectvalue(hoveropt);
  } else if (!hoveropt && (event.keyCode === 13 || event.keyCode === 9)) {
    // return || tab pressed in new value thing hover
    inputdone();
  } else if (optorder.length && event.keyCode === 40) {
    // down arrow key
    if (hoveropt && optorderindex[hoveropt] + 1 <= optorder.length) {
      // else bottom line, do nothing
      hoveropt = optorder[optorderindex[hoveropt] + 1];
    } else if (!hoveropt) {
      hoveropt = optorder[0];
    }
  } else if (optorder.length && event.keyCode === 38) {
    // up arrow key
    hoveropt = hoveropt && optorderindex[hoveropt] > 0 ? optorder[optorderindex[hoveropt] - 1] : false;
  } else if (!intext.length) {
    hoveropt = false;
    options = Object.fromEntries(Object.entries(fixedoptions));
    optorder = Object.keys(options);
  } else if (event.key.length > 1 && !(event.keyCode === 8 || event.keyCode === 46)) {
    // special key without modification effect (e.g. alt), not backspace/delete
    return
  } else if (intext.length > 2 && fetchUrl) {
    selectval = '';
    options = await getJSON(`${fetchUrl}?q=${intext}`);
    fetchedData = Object.assign({}, options);
    delete(options.ok);
    optorder = Object.keys(options);
    typing = true;
  } else if (!fetchUrl && fixedoptions && intext) {
    selectval = '';
    options = Object.fromEntries(Object.entries(fixedoptions).filter(x => x[1].name.toLowerCase().indexOf(intext.toLowerCase()) > -1));
    const keys = Object.keys(options);
    optorder = fixedorder.length ? fixedorder.filter(x => keys.indexOf(x.toString()) > -1) : keys;
    typing = true;
  } else if (!fetchUrl && fixedoptions) {
    options = Object.fromEntries(Object.entries(fixedoptions));
    optorder = fixedorder.length ? fixedorder : Object.keys(options);
    typing = true;
  }
  if (!optorder.length) { hoveropt = false };
}

function starttyping() {
  const keys = Object.keys(options);
  optorder = fixedorder.length ? fixedorder : keys;
  options = fixedorder.length ? fixedoptions : options;
  typing = true;
  placeholder = selectval ? niceName(selectval) : '';
}
 
</script>

<div class="control has-icons-right" tabindex="0">
  <input type="text" on:blur={inputdone} class="input is-narrow" placeholder={placeholder} on:keyup|preventDefault|stopPropagation={handleKeyInput} on:focus={starttyping} bind:value={intext}>
  <span class="icon is-right"><i class="fas fa-chevron-down"></i></span>

  {#if typing}
  <div class="select is-multiple">
    <select multiple on:mousedown={e => mouseSelect = true} >
      {#if !optorder.length}
      <option disabled>Type more or type less...</option>
      {/if}
      {#each optorder as optid} 
      <option selected={optid===hoveropt} value={optid} on:mouseup={e => selectvalue(optid)} on:mousemove={e => hoveropt=optid}>{niceName(options[optid])}</option>
      {/each}
  </select>
  </div>
  {/if}
</div>
