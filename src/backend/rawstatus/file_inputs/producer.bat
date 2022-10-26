# This can be run using the scheduler, or possibly by hand

REM change dir to script dir
cd %~dp0

call venv\Scripts\activate
python.exe upload.py --config transfer_config.json
