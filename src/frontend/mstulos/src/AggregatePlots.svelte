<script>
import { onMount } from 'svelte';
import { postJSON } from '../../datasets/src/funcJSON.js'
import * as Plot from '@observablehq/plot';

// data is already top lvl on the document so need no passing in here
let plots
let errors = [];

async function fetchData() {
  let url = new URL('/mstulos/plotdata/peptides/', document.location);
  let expids = new Set();
  data.forEach(x => x.experiments.forEach(x => expids.add(x[0])));
  const post = {expids: Array.from(expids), pepids: data.map(x => x.id )}
  const resp = await postJSON(url, post);
  return resp;
}


async function replot() {
  const fetched = await fetchData();
  const pep_re = /[A-Z\[\]]/gi;

  let ms1plot_bareseq;
  let ms1plot_modseq;

  // MS1 plot
  try {
    ms1plot_bareseq = Plot.plot({
      title: 'MS1 area by bare peptides (mods summed)',
      width: plots.offsetWidth - 20,
      color: {legend: true},
      y: {grid: true},

      marks: [Plot.rectY(fetched.samples, Plot.binX(
        {y2: 'count'},
        {thresholds: 100, x: 'ms1',
          fill: 'seq', 
          mixBlendMode: 'multiply'},
      )),
      ]
    });
  } catch (error) {
    errors.push(`For MS1 by bare peptides: ${error}`);
  }

  try {
    ms1plot_modseq = Plot.plot({
      title: 'MS1 area by modified peptides',
      width: plots.offsetWidth - 20,
      color: {legend: true},
      y: {grid: true},

      marks: [Plot.rectY(fetched.samples, Plot.binX(
        {y2: 'count'},
        {thresholds: 100, x: 'ms1',
          fill: (d) => 
          {
            let lastpos_modseq = d.modpos.reduce(
              (previx_modseq, pos, ix) => 
              [pos, previx_modseq[1] + d.seq.slice(previx_modseq[0], pos) + `(${fetched.modifications[d.mods[ix]]})`],
              
              [0, ''],
            )
            return `${lastpos_modseq[1]}${d.seq.slice(lastpos_modseq[0])}`;
          },
          mixBlendMode: 'multiply'},
      )),
      ]
    });
  } catch (error) {
    errors.push(`For MS1 by mod. peptides: ${error}`);
  }

  if (ms1plot_bareseq) {
    plots?.append(ms1plot_bareseq);
  }
  if (ms1plot_modseq) {
    plots?.append(ms1plot_modseq);
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
  <h4 class="title is-4">Peptide aggregates</h4>
</div>
