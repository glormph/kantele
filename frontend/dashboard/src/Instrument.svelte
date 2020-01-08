<script>
export let bokeh_code;
</script>

<div class="bk-root">
  <h5 class="title is-5"># Identifications</h5>
  <div class="bk-plotdiv" id={bokeh_code.div.amount_peptides.elementid}></div>
  <hr>
  <h5 class="title is-5"># PSMs</h5>
  <div class="bk-plotdiv" id={bokeh_code.div.amount_psms.elementid}></div>
  <hr>
  <h5 class="title is-5">Peptide precursor areas</h5>
  <div class="bk-plotdiv" id={bokeh_code.div.precursorarea.elementid}></div>
  <hr>
  <h5 class="title is-5">PSM MSGFScore</h5>
  <div class="bk-plotdiv" id={bokeh_code.div.msgfscore.elementid}></div>
  <hr>
  <h5 class="title is-5">Precursor error (ppm)</h5>
  <div class="bk-plotdiv" id={bokeh_code.div.prec_error.elementid}></div>
  <hr>
  <h5 class="title is-5">Retention time (min)</h5>
  <div class="bk-plotdiv" id={bokeh_code.div.rt.elementid}></div>
  <hr>
</div>
