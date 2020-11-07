<script>
import { schemeSet1 } from 'd3-scale-chromatic';

import BoxPlot from './BoxPlot.svelte';
import LinePlot from './LinePlot.svelte';

export let qcdata;

let identplot;
let psmplot;
let fwhmplot;
let pepms1plot;
let ionmobplot;
let msgfplot;
let rtplot;
let perrorplot;

export function parseData() {
  qcdata.psms.data.map(d => Object.assign(d, d.day = new Date(d.day)));
  qcdata.psms.series = new Set(qcdata.psms.data.map(d => Object.keys(d)).flat());
  qcdata.ident.data.map(d => Object.assign(d, d.day = new Date(d.day)));
  qcdata.ident.series = new Set(qcdata.ident.data.map(d => Object.keys(d)).flat());
  qcdata.fwhm.data.map(d => Object.assign(d, d.day = new Date(d.day)));
  qcdata.precursorarea.data.map(d => Object.assign(d, d.day = new Date(d.day)));
  qcdata.ionmob.data.map(d => Object.assign(d, d.day = new Date(d.day)));
  qcdata.msgfscore.data.map(d => Object.assign(d, d.day = new Date(d.day)));
  qcdata.rt.data.map(d => Object.assign(d, d.day = new Date(d.day)));
  qcdata.prec_error.data.map(d => Object.assign(d, d.day = new Date(d.day)));
  //qcdata..data.map(d => Object.assign(d, d.day = new Date(d.day)));
  setTimeout(() => {
    identplot.plot();
    psmplot.plot();
    fwhmplot.plot();
    pepms1plot.plot();
    ionmobplot.plot();
    msgfplot.plot();
    perrorplot.plot();
    rtplot.plot();
  }, 0);
}
</script>

<div class="bk-root">
  <h5 class="title is-5">Identifications</h5>
  <LinePlot bind:this={identplot} plotid="ident" colorscheme={schemeSet1} data={qcdata.ident.data} series={qcdata.ident.series} xkey={qcdata.ident.xkey} xlab="Date" ylab="Amount PSMs/scans" />
  <hr>
  <h5 class="title is-5"># PSMs</h5>
  <LinePlot bind:this={psmplot} plotid="psms" colorscheme={schemeSet1} data={qcdata.psms.data} series={qcdata.psms.series} xkey={qcdata.psms.xkey} xlab="Date" ylab="Amount" />
  <hr>
  <h5 class="title is-5">Peptide precursor areas</h5>
    <BoxPlot bind:this={pepms1plot} plotid="pepms1" colorscheme={schemeSet1} data={qcdata.precursorarea.data} xkey={qcdata.precursorarea.xkey} xlab="Date" ylab="" />
  <hr>
  {#if 'fwhm' in qcdata}
  <h5 class="title is-5">Peak width half max</h5>
    <BoxPlot bind:this={fwhmplot} plotid="fwhm" colorscheme={schemeSet1} data={qcdata.fwhm.data} xkey={qcdata.fwhm.xkey} xlab="Date" ylab="" />
  <hr>
  {/if}
  {#if 'ionmob' in qcdata}
  <h5 class="title is-5">Ion mobility</h5>
    <BoxPlot bind:this={ionmobplot} plotid="ionmob" colorscheme={schemeSet1} data={qcdata.ionmob.data} xkey={qcdata.ionmob.xkey} xlab="Date" ylab="" />
  <hr>
  {/if}
  <h5 class="title is-5">PSM MSGFScore</h5>
    <BoxPlot bind:this={msgfplot} plotid="msgf" colorscheme={schemeSet1} data={qcdata.msgfscore.data} xkey={qcdata.msgfscore.xkey} xlab="Date" ylab="" />
  <hr>
  <h5 class="title is-5">Precursor error (ppm)</h5>
    <BoxPlot bind:this={perrorplot} plotid="precerror" colorscheme={schemeSet1} data={qcdata.prec_error.data} xkey={qcdata.prec_error.xkey} xlab="Date" ylab="" />
  <hr>
  <h5 class="title is-5">Retention time (min)</h5>
    <BoxPlot bind:this={rtplot} plotid="retentiontime" colorscheme={schemeSet1} data={qcdata.rt.data} xkey={qcdata.rt.xkey} xlab="Date" ylab="" />
  <hr>
</div>
