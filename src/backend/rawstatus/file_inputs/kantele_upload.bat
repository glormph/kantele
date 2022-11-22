echo Started upload script

python -m venv .kantele-upload-venv
call .kantele-upload-venv\Scripts\activate
pip install requests requests_toolbelt

python "%~dp0\upload.py" --files "%1"
