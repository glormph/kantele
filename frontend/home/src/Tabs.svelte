<script>

export let tabshow; 

let tabs = ['Datasets', 'Projects', 'Analyses', 'Files', 'Jobs'];

</script>

<div class="content">
  <div class="tabs is-toggle is-centered is-small">
    <ul>
      {#each tabs as tab}
      <li class={tabshow === tab ? 'is-active' : ''}>
        <a href={`#/${tab.toLowerCase()}`}><span>{tab}</span></a>
      </li>
      {/each}
    </ul>
  </div>
</div>
