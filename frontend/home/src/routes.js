import Datasets from './Datasets.svelte'
import Jobs from './Jobs.svelte'
import Files from './Files.svelte'
import Analyses from './Analysis.svelte'

const routes = {
    '/': Datasets,
    '/datasets': Datasets,
    '/jobs': Jobs,
    '/files': Files,
    '/analyses': Analyses,
}

export default routes;
