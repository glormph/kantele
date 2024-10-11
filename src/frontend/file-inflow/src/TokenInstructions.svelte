<script>
export let fileType;

const isWindows = navigator.appVersion.toLowerCase().indexOf('win') != -1 ? 1 : 0;

</script>


<h5 class="subtitle is-5">Instructions for upload of big files with token</h5>
<div class="content">
  You can upload your own larger {fileType} files to storage. For this you need the following:
  <ul>
    <li>Python &gt;=3.6</li>
    <li>
      <a href="/files/datainflow/download/?client=user&windows={isWindows}">These uploading scripts for {isWindows ? 'Windows': 'MacOS/Linux'}</a> (click <a href="download/?client=user&windows={isWindows ? 0 : 1}">here</a> for {isWindows ? 'MacOS/Linux' : 'Windows'})
    </li>
    <li>an upload token (above)</li>
  </ul>
  If not done previously, download and extract the upload scripts. Then <code>chdir</code> to the directory 
  containing them, and run e.g.:
  <p>
  <code>
    {#if isWindows}
    kantele_upload.bat path\to\file.fa
    {:else}
    bash kantele_upload.sh /path/to/file.fa
    {/if}
  </code>
  </p>
  This will create a python virtual environment in your current directory.
  You will be asked for the upload token, paste it and let it run. The same token
  can be used for multiple file uploads of the same file type, in which case you can
  use <code>*.fa</code>. All files uploaded 
  using a certain token will be stored similarly (archived or active).
  
  The files must be transferred <b>one at a time</b>. You can also upload a folder, but it will be zipped by the upload, and stay zipped in storage. (Please keep a sensible total folder size, 500GB is not sensible!). For this, point the upload script to the folder instead of a raw file:
        
  <p>
  <code>
    {#if isWindows}
    kantele_upload.bat path\to\folder_containing_experiment
    {:else}
    bash kantele_upload.sh /path/to/folder_containing_experiment
    {/if}
  </code>
  </p>
  
  Depending on the file type, folders will be unzipped on the storage archive (e.g. <code>.d</code> raw data), or left zipped (e.g. microscopy).
</div>
