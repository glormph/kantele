<script>
import { createEventDispatcher } from 'svelte';
const dispatch = createEventDispatcher();

const now = new Date(Date.now());
let daysago = 0;
let todate = new Date(now);
todate.setDate(todate.getDate() - daysago);
let displaydate = todate.toISOString().slice(0, 10);
let newdate;
$: {
  newdate = new Date(now);
  newdate.setDate(newdate.getDate() - daysago);
  if (newdate.getTime() !== todate.getTime()) {
    todate = newdate;
    displaydate = todate.toISOString().slice(0, 10);
  }
}
let firstday = 0;
$: firstday = Math.round((now.getTime() - todate.getTime()) / (1000 * 60 * 60 * 24));

let maxdays = 30;

function changeDateRange() {
  dispatch('updatedates', {showdays: maxdays, firstday: firstday});
}
</script>

<div class="level">
  <div class="level-left">
    <div class="level-item">
      <a class="button is-info is-small" on:click={changeDateRange}>Refresh</a>
    </div>
    <div class="level-item">
      Days to show: <input class="input" type="number" size="1" bind:value={maxdays} on:change={changeDateRange}>
    </div>
    <div class="level-item">
<input type="range" max="100" min="1" step="1" bind:value={maxdays} on:change={changeDateRange}>
    </div>
    <div class="level-item">
      Last day: <input class="input" type="date" bind:value={displaydate} on:change={changeDateRange}>
    </div>
    <div class="level-item">
<input type="range" max="100" min="0" step="1" bind:value={daysago} on:change={changeDateRange}>
    </div>
  </div>
</div>
