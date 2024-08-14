<script>
import { onMount } from 'svelte';
import { postJSON } from '../../datasets/src/funcJSON.js'
import * as Plot from '@observablehq/plot';

// data is already top lvl on the document so need no passing in here
let plots
let errors = [];

async function fetchData() {
  let url = new URL('/mstulos/plotdata/psms/', document.location);
  let expids = new Set();
  data.forEach(x => x.experiments.forEach(x => expids.add(x[0])));
  const post = {expids: Array.from(expids), pepids: data.map(x => x.id )}
  const resp = await postJSON(url, post);
  return resp;
}


async function replot() {
  const fetched = await fetchData();
  const pep_re = /[A-Z\[\]]/gi;

  let scoreplot_bareseq;
  let fdrplot_modseq;

  // Score by seq/charge plot
  try {
    let previx = 0;
    scoreplot_bareseq = Plot.plot({
      title: 'Score by seq/charge',
      width: plots.offsetWidth - 20,
      y: {grid: true},
      color: {legend: true},

      marks: [Plot.rectY(fetched.psms, Plot.binX(
        {y: 'count'},
        {
          thresholds: 100, x: 'score', 
          fill: (d) => {
            let lastpos_modseq = d.modpos.reduce(
              (previx_modseq, pos, ix) => 
              [pos, previx_modseq[1] + d.seq.slice(previx_modseq[0], pos) + `(${fetched.modifications[d.mods[ix]]})`],
              
              [0, ''],
            )
            return `${lastpos_modseq[1]}${d.seq.slice(lastpos_modseq[0])}+${d.charge}`;
          },
          mixBlendMode: 'multiply',
        }
        ))
      ]
    });
  } catch (error) {
    errors.push(`For score by modseq/charge: ${error}`);
  }

  if (scoreplot_bareseq) {
    plots?.append(scoreplot_bareseq);
  }
  if (fdrplot_modseq) {
    plots?.append(fdrplot_modseq);
  }
  errors = [...errors];
}

onMount(async() => {
  replot();
});

</script>

  {#if errors.length}
  <article class="message is-danger">
    <div class="message-body">
    {errors.join('\n')}
    </div>
  </article>
  {/if}

<div class="box" bind:this={plots} id="plots">
  <h4 class="title is-4">PSM aggregates</h4>
</div>
