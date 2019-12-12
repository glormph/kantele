# This can be run using the scheduler, or possibly by hand

set FILETYPE_ID={{ filetype_id }} 
set RAW_IS_FOLDER={{ is_folder }} 
set OUTBOX='{{ datadisk }}/outbox'
set DONEBOX='{{ datadisk }}/donebox'
set CLIENT_ID={{ client_id }}
set KANTELEHOST={{ host }}
set KEYFILE={{ key }}
set SCP_FULL={{ scp_full }} # name@server.com:/home/storage
set KEEPRUNNING='yes'

call venv\Scripts\activate
python.exe producer.py
