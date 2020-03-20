<script>

export let value;
export let fieldtype;
export let help = '';
export let icon;
export let color

</script>

{#if fieldtype === 'tag'}
  {#if color}
  <span class={`tag ${color[value]}`}>{value}</span>
  {:else}
  <span class="tag is-info">{value}</span>
  {/if}
{:else if fieldtype === 'bool'}
<span class="has-icon">
  {#if value}
  <i class="fa fa-check has-text-success"></i>
  {:else}
  -
  {/if}
</span>
{:else if fieldtype === 'icon'}
<span title={help} class={`icon is-small is-info`}><i class={`fa fa-${icon}`}></i></span>
{:else if fieldtype === 'state'}
<span class={`icon is-small ${color[value]}`}><i class="fa fa-square"></i></span>
{:else if fieldtype === 'button'}
  {#if value.slice(0, 2) == '__'}
  <span class="icon is-small">
    <i class={`fa fa-${fieldname.slice(2)}`}></i>
  </span>
  {:else}
  <button class="button is-small">{value}</button>
  {/if}
{:else}
{value}
{/if}
