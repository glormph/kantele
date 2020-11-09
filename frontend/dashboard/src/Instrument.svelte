<script>
import { schemeSet1 } from 'd3-scale-chromatic';
import { createEventDispatcher } from 'svelte';

import BoxPlot from './BoxPlot.svelte';
import LinePlot from './LinePlot.svelte';
import DateSlider from './DateSlider.svelte';

const dispatch = createEventDispatcher();

export let qcdata;
export let instrument_id;


let identplot;
let psmplot;
let fwhmplot;
let pepms1plot;
let ionmobplot;
let msgfplot;
let rtplot;
let perrorplot;

function reloadData(maxdays, firstday) {
  dispatch('reloaddata', {instrument_id: instrument_id, showdays: maxdays, firstday: firstday});
}

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

<div>
  <DateSlider on:updatedates={e => reloadData(e.detail.showdays, e.detail.firstday)} />
  <hr>
  
  <div class="tile is-ancestor">
    <div class="tile">
      <div class="content">
        <h5 class="title is-5">Identifications</h5>
        <LinePlot bind:this={identplot} colorscheme={schemeSet1} data={qcdata.ident.data} series={qcdata.ident.series} xkey={qcdata.ident.xkey} xlab="Date" ylab="Amount PSMs/scans" />
      </div>
    </div>
    <div class="tile">
      <div class="content">
        <h5 class="title is-5"># PSMs</h5>
        <LinePlot bind:this={psmplot} colorscheme={schemeSet1} data={qcdata.psms.data} series={qcdata.psms.series} xkey={qcdata.psms.xkey} xlab="Date" ylab="Amount" />
      </div>
    </div>
  </div>
  <hr>
  <div class="tile is-ancestor">
    <div class="tile">
      <div class="content">
        <h5 class="title is-5">Peptide precursor areas</h5>
        <BoxPlot bind:this={pepms1plot} colorscheme={schemeSet1} data={qcdata.precursorarea.data} xkey={qcdata.precursorarea.xkey} xlab="Date" ylab="" />
      </div>
    </div>
    <div class="tile">
      <div class="content">
        <h5 class="title is-5">Precursor error (ppm)</h5>
        <BoxPlot bind:this={perrorplot} colorscheme={schemeSet1} data={qcdata.prec_error.data} xkey={qcdata.prec_error.xkey} xlab="Date" ylab="" />
      </div>
    </div>
  </div>
  <hr>
  <div class="tile is-ancestor">
    <div class="tile">
      <div class="content">
        <h5 class="title is-5">Retention time (min)</h5>
        <BoxPlot bind:this={rtplot} colorscheme={schemeSet1} data={qcdata.rt.data} xkey={qcdata.rt.xkey} xlab="Date" ylab="" />
      </div>
    </div>
    <div class="tile">
      <div class="content">
        <h5 class="title is-5">PSM MSGFScore</h5>
        <BoxPlot bind:this={msgfplot} colorscheme={schemeSet1} data={qcdata.msgfscore.data} xkey={qcdata.msgfscore.xkey} xlab="Date" ylab="" />
      </div>
    </div>
  </div>
  <hr>
  <div class="tile is-ancestor">
    <div class="tile">
      <div class="content">
        {#if 'fwhm' in qcdata}
        <h5 class="title is-5">Peak width half max</h5>
        <BoxPlot bind:this={fwhmplot} colorscheme={schemeSet1} data={qcdata.fwhm.data} xkey={qcdata.fwhm.xkey} xlab="Date" ylab="" />
        {/if}
      </div>
    </div>
    <div class="tile">
      <div class="content">
        {#if 'ionmob' in qcdata}
        <h5 class="title is-5">Ion mobility</h5>
        <BoxPlot bind:this={ionmobplot} colorscheme={schemeSet1} data={qcdata.ionmob.data} xkey={qcdata.ionmob.xkey} xlab="Date" ylab="" />
        {/if}
      </div>
    </div>
  </div>
</div>
