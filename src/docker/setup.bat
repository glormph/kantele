echo Setting up virtual environment for filetransfer
python -m venv venv
call venv\Scripts\activate
echo Installing python libraries
pip install charset_normalizer-2.1.1-py3-none-any.whl
pip install idna-3.4-py3-none-any.whl 
pip install certifi-2022.9.14-py3-none-any.whl
pip install urllib3-1.26.12-py2.py3-none-any.whl
pip install requests-2.28.1-py3-none-any.whl
pip install requests_toolbelt-0.9.1-py2.py3-none-any.whl
pip install psutil-6.1.0-cp37-abi3-win_amd64.whl

echo schtasks /create /sc ONLOGON /tn kantele_filetransfer /tr "python %cd%/transfer.bat" > tasksetup.bat
echo echo Created task in task scheduler >> tasksetup.bat
echo pause >> tasksetup.bat
echo Done setting up, please run tasksetup.bat as administrator 
pause

