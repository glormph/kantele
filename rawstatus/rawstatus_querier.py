import os
from db import dbaccess
dbase = dbaccess.DatabaseAccess()

def get_statuses(fns):
    report = {}
    for fn in fns:
        status,date = 'not found', '-'
        fname = os.path.splitext(fn)[0]
        dbrec = dbase.get_rawfile_processed_status(fname)
        if dbrec and fname + dbrec['files'][fname]['extension'] == fn:
            if dbrec['general_info']['status'] == 'done':
                status = 'done'
            date = dbrec['general_info']['date']
        report[fn] = (status, date)
    return report
