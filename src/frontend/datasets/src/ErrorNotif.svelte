<script>

export let errors;
export let cssclass = '';
</script>

<style>
  .sticky {
    position: sticky;
    position: -webkit-sticky;
    top: 20px;
    z-index: 1000;
  }
</style>

{#if errors.length}
<div class={`notification is-danger ${cssclass}`}>
  <ul>
    {#each errors as error}
    <li>&bull; {error}</li>
    {/each}
  </ul>
</div>
{/if}
