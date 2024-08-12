<script>
import { onMount } from 'svelte';
import { postJSON } from '../../datasets/src/funcJSON.js'
import * as Plot from '@observablehq/plot';

// data is already top lvl on the document so need no passing in here
let plots

async function fetchData() {
  let url = new URL('/mstulos/plotdata/', document.location);
  let expids = new Set();
  data.forEach(x => x.experiments.forEach(x => expids.add(x[0])));
  const post = {expids: Array.from(expids), pepids: data.map(x => x.id )}
  const resp = await postJSON(url, post);
  return resp;
}


async function replot() {
  const fetched = await fetchData();
  const pep_re = /[A-Z\[\]]/gi;

  // MS1 plot
  let ms1plot = Plot.plot({
    width: plots.offsetWidth - 20,
    x: {axis: null},
    y: {tickFormat: 's', grid: true, }, // scientific ticks
    marks: [Plot.barY(fetched.samples, {
      y: 'ms1',
      x: (d) => `${d.seq}_${d.cname}`,
      fx: (d) => fetched.experiments[d.exp],
      fill: 'seq',
    }),
      Plot.tip(fetched.samples, Plot.pointer({
        x: (d) => `${d.seq}_${d.cname}`,
        fx: (d) => fetched.experiments[d.exp],
        maxRadius: 200,
        title: (d) => [d.seq, '', 
          d.mod.replaceAll(pep_re, '')
          .split(',')
          .map(x => x.trim().split(':'))
          .map(x => [d.seq[x[0]], x[0], ':', fetched.modifications[x[1]]].join(''))
          .join(', '),
          fetched.experiments[d.exp],
          `${fetched.conditions[d.ctype]}: ${d.cname}`, `MS1: ${d.ms1}`, ].join('\n')}))
    ]
  });

  // FDR plot
  let qplot = Plot.plot({
    width: plots.offsetWidth - 20,
    x: {axis: null},
    y: {grid: true},
    marks: [Plot.barY(fetched.samples, {
      y: 'qval',
      x: (d) => `${d.seq}_${d.cname}`,
      fx: (d) => fetched.experiments[d.exp],
      fill: 'seq',
    }),
      Plot.tip(fetched.samples, Plot.pointer({
        x: (d) => `${d.seq}_${d.cname}`,
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

  // Isobaric plot
  let isoplot = Plot.plot({
    width: plots.offsetWidth - 20,
    x: {axis: null},
    y: {grid: true},
    marks: [Plot.barY(fetched.isobaric, {
      y: 'value',
      //x: (d) => `${d.peptide}_${d.cname}_${fetched.chmap[d.ch].name}`,
      x: (d) => `${fetched.molmap[d.peptide].seq}_${d.ch}`,
      fx: (d) => fetched.experiments[fetched.chmap[d.ch].exp],
      fill: (d) => fetched.molmap[d.peptide].seq,
    }),
      Plot.tip(fetched.isobaric, Plot.pointer({
        y: 0,
        x: (d) => `${fetched.molmap[d.peptide].seq}_${d.ch}`,
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

  plots?.append(qplot);
  plots?.append(ms1plot);
  if (fetched.isobaric) {
    plots?.append(isoplot);
  }

}

onMount(async() => {
  replot();
});

  </script>

<button class="button">Plot {nr_filtered_pep} peptide{nr_filtered_pep > 1 ? 's' : ''} over {nr_filtered_exp} experiment{nr_filtered_exp > 1 ? 's' : ''}</button>
<button class="button">Plot aggregates</button>

  <div class="box" bind:this={plots} id="plots"></div>

