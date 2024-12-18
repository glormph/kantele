<script>
import { createEventDispatcher } from 'svelte';
const dispatch = createEventDispatcher();

export let param;

function edited() { dispatch('edited');}

</script>

<div class="field">
  <label class="label">{param.title}</label>
  <div class="control">
    {#if param.inputtype === 'select'}
    <div class="select"> 
      <select bind:value={param.model} on:change={edited}>
        <option value="">Not used</option>
        {#each param.fields as option}
        <option value={option.value}>{option.text}</option>
        {/each}
      </select>
    </div>
    {:else if param.inputtype === 'text'}
    <input type="text" class="input" placeholder={param.placeholder} bind:value={param.model} on:change={edited}>
    {:else if param.inputtype === 'number'}
    <input type="number" class="input" placeholder={param.placeholder} bind:value={param.model} on:change={edited}>
    {:else if param.inputtype === 'checkbox'}
    {#each param.fields as option}
    <div class="control">
      <input bind:checked={option.checked} on:change={edited} type="checkbox">{option.text}
    </div>
    {/each}
    {/if}
  </div>
</div>
