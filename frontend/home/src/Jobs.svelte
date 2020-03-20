<script>

import {querystring} from 'svelte-spa-router';
import { onMount } from 'svelte';
import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'
import Table from './Table.svelte'
import Tabs from './Tabs.svelte'

let job_ids;
try {
  const qs = Object.fromEntries($querystring.split('&').map(x => x.split('=')));
  job_ids = qs.jobids.split(',');
} catch {
  job_ids = [];
}

let jobs = {};
let order = [];
let selectedjobs = [];
let loadingJobs = false;

const tablefields = [
  {id: 'state', name: '__hourglass-half', type: 'state', multi: false},
  {id: 'name', name: 'Job name', type: 'str', multi: false},
  {id: 'files', name: '', help: 'Files', type: 'icon', icon: 'database', multi: false, links: 'fn_ids', linkroute: '#/files?fnids='},
  {id: 'analysis', name: '', help: 'Analysis', type: 'icon', icon: 'cogs', multi: false, links: 'analysis', linkroute: '#/analyses?anids='},
  {id: 'datasets', name: '', help: 'Datasets', type: 'icon', icon: 'clipboard-list', multi: false, links: 'dset_ids', linkroute: '#/datasets?dsids='},
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

async function loadJobs(url) {
  jobs = {};
  order = [];
  loadingJobs = true;
  const result = await getJSON(url);
	jobs = result.items;
	order = result.order;
  loadingJobs = false;
}

async function fetchJobs(jobids) {
	let url = '/show/jobs/'
	url = jobids.length ? url + `?jobids=${jobids.join(',')}` : url;
  loadJobs(url);
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


onMount(async() => {
  fetchJobs(job_ids);
})
</script>

<Tabs tabshow="Jobs" />
<div class="content is-small">
  <Table bind:selected={selectedjobs} loading={loadingJobs} getdetails={getJobDetails} fixedbuttons={[]} fields={tablefields} order={order} trs={jobs} statecolors={statecolors}/>
</div>
