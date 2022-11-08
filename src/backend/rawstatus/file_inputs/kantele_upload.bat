set upfile=%1

IF NOT EXIST "%upfile%" (
    echo File "%upfile" does not exist, is the path correct?
    exit
)

echo Started upload script

python3 -m venv .kantele-upload-venv
call .kantele-upload-venv\Scripts\activate
pip install requests requests_toolbelt

python upload.py --file "%upfile%"
