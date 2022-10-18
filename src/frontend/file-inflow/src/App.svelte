<script>

import { getJSON, postJSON } from '../../datasets/src/funcJSON.js'

let ft_selected = false;
//let token = false;
let token = false;
let onlyArchive = false;

async function createToken() {
  const resp = await postJSON('../token/', {'ftype_id': ft_selected});
  if (resp.error) {
    console.log('error');
    // FIXME
  } else {
    console.log(resp);
    token = resp;
  }

}
</script>

<style>
.test{
  font-color: black;
}
</style>

<div class="columns">
  <div class="column">
    <div class="box">
      <h5 class="title is-5">Automated file transfer</h5>
      <h5 class="subtitle is-5">for instruments</h5>
      <form action="download/" method="GET">
        <div class="field">
          <label class="label">Datadisk letter</label>
          <input type="hidden" name="client" value="instrument">
          <input type="text" name="datadisk" class="input" placeholder="Drive letter for data, e.g. D">
        </div>
      
        <div class="field">
          <label class="label">Producer</label>
          <div class="select">
            <select name="prod_id">
              {#each Object.entries(producers) as [pid, prod]}
              <option value={pid}>{prod}</option>
              {/each}
            </select>
          </div>
        </div>
        <div class="field">
          <label class="checkbox">
            <input name="configonly" value="true" type="checkbox">
            Only download configuration (not for new instruments, uploader updates)
          </label>
        </div>
        <input class="button" type="submit" value="Download package">
      </form>

      <h5 class="subtitle is-5">Instructions</h5>
      <ul>
        <li>&bull; Install <a href="https://www.python.org/downloads/">Python >=3.6</a> on the machine, for all users (not as an admin). When installing, make sure to check "add to PATH"</li>
        <li>&bull; Fill in the above form and download the zip file</li>
        <li>&bull; Move and unzip the file to an appropriate location, preferably on the Desktop for easy updating</li>
        <li>&bull; Run <code>setup.bat</code></li>
        <li>&bull; To create scheduled tasks, run the generated file (with administrator rights) <code>tasksetup.bat</code></li>
        <li>&bull; Run<code>transfer.bat</code></li>
      </ul>
    </div>
    <div class="section">
      <h5 class="subtitle is-5">Config updates</h5>
      <ul>
        <li>&bull; Fill in the above form, tick the config-only box and download the <code>transfer.bat</code> file</li>
        <li>&bull; Replace original bat file with the new file</li>
        <li>&bull; Stop running transfer program</li>
        <li>&bull; Run<code>transfer.bat</code></li>
      </ul>
    </div>
  </div>
  <div class="column">
    <div class="box">
      <h5 class="title is-5">Upload your files</h5>
      <h5 class="subtitle is-5">Get an upload authentication token</h5>
      Administrators can enable uploads of specific file types.

      {#if Object.keys(filetypes).length}
      <div class="field">
        <div class="select">
          <select bind:value={ft_selected}>
            <option value={false}>Select a filetype</option>
            {#each Object.entries(filetypes) as [fid, name]}
            <option value={fid}>{name}</option>
            {/each}
          </select>
        </div>
        {#if ft_selected}
        <div on:click={createToken} class="button">Create token</div>
        {/if}
      </div>
      <div clas="field">
        <div class="checkbox">
          <input type="checkbox" bind:checked={onlyArchive}>
          <label clas="checkbox">Only store in archive/backup</label>
        </div>
      </div>
        {#if token}
        <hr>
        <div>
          <label class="label">Here is your token</label>
          <input class="input" value={token.user_token} />
          It will expire {token.expires}
        </div>
      {/if}
        {:else}
        No upload of any file type is currently enabled!
        {/if}
      <hr>
      <h5 class="subtitle is-5">Instructions</h5>
      You can upload your own raw files to totoro. For this you need the following:
      <ul>
        <li>&bull; Linux or MacOS terminal</li>
        <li>&bull; Python &gt;=3.6</li>
        <li>&bull; 
          <a href="download/?client=user">these uploading scripts</a>
        </li>
        <li>&bull; an upload token (above)</li>
      </ul>
      <hr>
      If not done previously, download and extract the upload scripts. Then <code>chdir</code> to the directory 
      containing them, and run:
      <p>
        <code>bash kantele_upload.sh /path/to/rawfile.raw</code>
      </p>
      This will create a python virtual environment in your current directory.
      You will be asked for the upload token, paste it and let it run. The same token
      can be used for multiple file uploads of the same file type. All files uploaded 
      using a certain token will be stored similarly (archived or active).
      <hr>
      For experiments with many small files, you can upload a folder, which will be zipped by the upload. (Please keep a sensible total folder size, 500GB is not sensible!). For this, point the upload script to the folder instead of a raw file:
      <p><code>bash kantele_upload.sh /path/to/folder_containing_experiment</code> </p>
      <p>
      Depending on the file type, folders will be unzipped on the storage archive (e.g. <code>.d</code> raw data), or left zipped (e.g. microscopy).
      </p>
      <hr>

    </div>
  </div>
</div>
