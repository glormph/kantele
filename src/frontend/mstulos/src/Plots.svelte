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

function formatModseq(d, modmap) {
  let lastpos_modseq = d.modpos.reduce(
    (previx_modseq, pos, ix) => 
    [pos, previx_modseq[1] + d.seq.slice(previx_modseq[0], pos) + `(${modmap[d.mods[ix]]})`],
    
    [0, ''],
  )
  return `${lastpos_modseq[1]}${d.seq.slice(lastpos_modseq[0])}`;
}


async function replot() {
  const fetched = await fetchData();
  const pep_re = /[A-Z\[\]]/gi;

  let ms1plot;
  let qplot;
  let isoplot;

  // MS1 plot
  try {
    ms1plot = Plot.plot({
      title: 'MS1 area',
      width: plots.offsetWidth - 20,
      x: {axis: null},
      y: {tickFormat: 's', type: 'log', grid: true, }, // scientific ticks
      marks: [Plot.barY(fetched.samples, {
        y1: 1,
        y2: 'ms1',
        x: (d) => `${d.mod}_${d.cname}`,
        fx: (d) => fetched.experiments[d.exp],
        fill: 'seq',
      }),
        Plot.tip(fetched.samples, Plot.pointer({
          x: (d) => `${d.mod}_${d.cname}`,
          fx: (d) => fetched.experiments[d.exp],
          maxRadius: 200,
          title: (d) => [d.seq, '', formatModseq(d, fetched.modifications),
            fetched.experiments[d.exp],
            `${fetched.conditions[d.ctype]}: ${d.cname}`, `MS1: ${d.ms1}`, ].join('\n')}))
      ]
    });
  } catch (error) {
    errors.push(`For MS1 plots: ${error}`);
  }

  // FDR plot
  try {
    qplot = Plot.plot({
      title: 'FDR (q-value)',
      width: plots.offsetWidth - 20,
      x: {axis: null},
      y: {grid: true},
      marks: [Plot.barY(fetched.samples, {
        y: 'qval',
        x: (d) => `${d.mod}_${d.cname}`,
        fx: (d) => fetched.experiments[d.exp],
        fill: 'seq',
      }),
        Plot.tip(fetched.samples, Plot.pointer({
          x: (d) => `${d.mod}_${d.cname}`,
          fx: (d) => fetched.experiments[d.exp],
          maxRadius: 200,
          title: (d) => [d.seq, '', 
            d.mod.replaceAll(pep_re, '')
            .split(',')
            .map(x => x.trim().split(':'))
            .map(x => [d.seq[x[0]], x[0], ':', fetched.modifications[x[1]]].join(''))
            .join(', '),
            fetched.experiments[d.exp],
            `${fetched.conditions[d.ctype]}: ${d.cname}`, `q-value: ${d.qval}`, ].join('\n')}))
      ]
    });
  } catch (error) {
    errors.push(`For FDR plots: ${error}`);
  }

  // Isobaric plot
  try {
    isoplot = Plot.plot({
      title: 'Isobaric values',
      width: plots.offsetWidth - 20,
      x: {axis: null},
      y: {grid: true},
      marks: [Plot.barY(fetched.isobaric, {
        y: 'value',
        x: (d) => `${fetched.molmap[d.peptide].mod}_${d.ch}`,
        fx: (d) => fetched.experiments[fetched.chmap[d.ch].exp],
        fill: (d) => fetched.molmap[d.peptide].seq,
      }),
        Plot.tip(fetched.isobaric, Plot.pointer({
          y: 0,
          x: (d) => `${fetched.molmap[d.peptide].mod}_${d.ch}`,
          fx: (d) => fetched.experiments[fetched.chmap[d.ch].exp],
          title: (d) => [fetched.molmap[d.peptide].seq, '', 
            d.value,
            fetched.molmap[d.peptide].mod.replaceAll(pep_re, '')
            .split(',')
            .map(x => x.trim().split(':'))
            .map(x => [fetched.molmap[d.peptide].seq[x[0]], x[0], ':', fetched.modifications[x[1]]].join(''))
            .join(', '),
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

  if (qplot) {
    plots?.append(qplot);
  }
  if (ms1plot) {
    plots?.append(ms1plot);
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
  <h4 class="title is-4">Peptides</h4>
</div>
