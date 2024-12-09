<script>
import { createEventDispatcher } from 'svelte';

const dispatch = createEventDispatcher();
export let title;
export let addIcon = false;

export let intext = '';



async function handleKeyInput(event) {
  // Takes care of key inputs, characters and backspace/delete
  if (event.keyCode === 13 && intext.length) {
    // return pressed
    // propagate signal, empty field again
    dispatch('newvalue', {'text': intext});
    intext = '';
  }
}


</script>

  <div class="field">
    {#if addIcon}
    <p class="control has-icons-left">
      <input class="input" type="text" bind:value={intext} placeholder="Add {title}" on:keyup={handleKeyInput} />
      <span class="icon is-small is-left">
        <i class="fas fa-plus"></i>
      </span>
    </p>
    {:else}
    <p class="control">
      <input class="input" type="text" bind:value={intext} placeholder="{title}" on:keyup={handleKeyInput} />
    </p>
    {/if}
  </div>
