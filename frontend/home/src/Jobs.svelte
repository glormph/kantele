<script>

import {querystring} from 'svelte-spa-router';
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'
import Table from './Table.svelte'
import Tabs from './Tabs.svelte'

let selectedjobs = [];
let errors = {};

const tablefields = [
  {id: 'state', name: '__hourglass-half', type: 'state', multi: false},
  {id: 'name', name: 'Job name', type: 'str', multi: false},
  {id: 'files', name: '', help: 'Files', type: 'icon', icon: 'database', multi: false, links: 'fn_ids', linkroute: '#/files'},
  {id: 'analysis', name: '', help: 'Analysis', type: 'icon', icon: 'cogs', multi: false, links: 'analysis', linkroute: '#/analyses'},
  {id: 'datasets', name: '', help: 'Datasets', type: 'icon', icon: 'clipboard-list', multi: false, links: 'dset_ids', linkroute: '#/datasets'},
  {id: 'usr', name: 'Users', type: 'str', multi: false},
  {id: 'date', name: 'Date', type: 'str', multi: false},
  {id: 'actions', name: 'Actions', type: 'button', multi: true},
];

const statecolors = {
  state: {
    wait: 'has-text-grey-light',
    pending: 'has-text-info',
    error: 'has-text-danger', 
    processing: 'has-text-warning', 
    done: 'has-text-success',
  },
}

async function getJobDetails(jobId) {
       const resp = await getJSON(`/show/job/${jobId}`);
  return `
    <p>${resp.files} files in job</p>
    ${resp.errmsg ? `<p>Error msg: ${resp.errmsg}</p>` : ''}
    <p>
    <span class="tag is-danger">${resp.tasks.error}</span>
    <span class="tag is-warning">${resp.tasks.procpen}</span>
    <span class="tag is-success">${resp.tasks.done}</span>
    </p>
  `;
}
</script>

<Tabs tabshow="Jobs" errors={errors} />
<Table tab="Jobs" bind:errors={errors} bind:selected={selectedjobs} fetchUrl="/show/jobs" findUrl="find/jobs" getdetails={getJobDetails} fixedbuttons={[]} fields={tablefields} inactive={[]} statecolors={statecolors}/>
