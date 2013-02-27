import os
from db import dbaccess
dbase = dbaccess.DatabaseAccess()

def get_statuses(fns):
    report = {}
    for fn in fns:
        status = 'not found'
        fname = os.path.splitext(fn)[0]
        dbrec = dbase.get_rawfile_processed_status(fname)
        if dbrec and fname + dbrec['files'][fname]['extension'] == fn:
            status = 'done'
        report[fn] = status
    return report
