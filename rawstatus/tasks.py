import hashlib
import os
from rawstatus.models import TransferredFile


def get_md5(fn_id):
    return  # FIXME
    entry = TransferredFile.objects.get(rawfile_id=fn_id)
    fnpath = os.path.join(entry.fnpath, entry.rawfile.name)
    hash_md5 = hashlib.md5()
    with open(fnpath, 'rb') as fp:
        for chunk in iter(lambda: fp.read(4096), b''):
            hash_md5.update(chunk)
    entry.md5 = hash_md5.hexdigest()
    entry.save()
