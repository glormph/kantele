<script>

export let notif;
export let closeWindow;

function handleKeypress(event) {
  if (event.keyCode === 27) { closeWindow(); }
}

</script>

<style>
.detailbox {
  position: absolute;
  top: 40px;
  width: 100%;
  height: 100%;
  z-index: 40; 
  pointer-events: none;
}

.modalbox {
  position: -webkit-sticky;
  position: sticky;
  padding: 100px;
  top: 0px;
  pointer-events: all;
}

.closebutton {
  position: absolute;
  top: 20px;
  right: 20px;
}

.notification {
  position: sticky;
  top: 20px;
  left: 20px;
  z-index: 50;
}
</style>

<svelte:window on:keyup={handleKeypress} />

<div class="detailbox">
  <div class="box modalbox">

    {#if Object.values(notif.errors).some(x => x === 1)}
    <div class="notification is-danger is-light errormsg"> 
        {#each Object.entries(notif.errors).filter(x => x[1] == 1).map(x=>x[0]) as error}
        <div>{error}</div>
        {/each}
    </div>
    {/if}
    {#if Object.values(notif.messages).some(x => x === 1)}
    <div class="notification is-success is-light errormsg"> 
        {#each Object.entries(notif.messages).filter(x => x[1] == 1).map(x=>x[0]) as message}
        <div>{message}</div>
        {/each}
    </div>
    {/if}
  
    <slot></slot>
    <button on:click={closeWindow()} class="button closebutton" aria-label="close"><span class="icon"><i class="fa fa-times"></i></span></button>
  </div>
</div>
