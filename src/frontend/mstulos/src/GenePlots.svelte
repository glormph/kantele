<script>
import { onMount } from 'svelte';
import { postJSON } from '../../datasets/src/funcJSON.js'
import * as Plot from '@observablehq/plot';

// data is already top lvl on the document so need no passing in here
let plots;
let errors = [];

async function fetchData() {
  let url = new URL('/mstulos/plotdata/genes/', document.location);
  let expids = new Set();
  data.forEach(x => x.experiments.forEach(x => expids.add(x[0])));
  const post = {expids: Array.from(expids), gids: data.map(x => x.id )}
  const resp = await postJSON(url, post);
  return resp;
}


async function replot() {
  const fetched = await fetchData();
  const pep_re = /[A-Z\[\]]/gi;

  let isoplot;

  // Isobaric plot
  try {
    isoplot = Plot.plot({
      title: 'Isobaric values',
      width: plots.offsetWidth - 20,
      x: {axis: null},
      y: {grid: true},
      marks: [Plot.barY(fetched.isobaric, {
        y: 'value',
        x: (d) => `${d.gene}_${d.ch}`,
        fx: (d) => fetched.experiments[fetched.chmap[d.ch].exp],
        fill: (d) => d.gene,
      }),
        Plot.tip(fetched.isobaric, Plot.pointer({
          y: 0,
          x: (d) => `${d.gene}_${d.ch}`,
          fx: (d) => fetched.experiments[fetched.chmap[d.ch].exp],
          title: (d) => [fetched.genemap[d.gene], '', 
            d.value,
            fetched.experiments[fetched.chmap[d.ch].exp],
            fetched.chmap[d.ch].name,
            fetched.chmap[d.ch].SAMPLE,
            fetched.chmap[d.ch].SAMPLESET,
            ].join('\n')}))
      ]
    });
  } catch (error) {
    errors.push(`For isobaric plots: ${error}`);
  }

  if (fetched.isobaric && isoplot) {
    plots?.append(isoplot);
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
  <h4 class="title is-4">Genes</h4>
</div>
