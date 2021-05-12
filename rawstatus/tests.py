from datetime import datetime
from django.test import TestCase, Client

from rawstatus import models as rm
from jobs import models as jm


class TransferStateTest(TestCase):
    def setUp(self):
        self.clientid = 'abcde'
        self.notclientid = 'qwerty'
        self.url = '/files/transferstate/'
        self.cl = Client()
        rm.ServerShare.objects.create(name='testserevr', uri='test.test', share='/home/test')
        rm.StoredFileType.objects.create(name='testft', filetype='tst')
        prod = rm.Producer.objects.create(name='prod1', client_id=self.clientid, shortname='p1')
        otherprod = rm.Producer.objects.create(name='otherprod1', client_id=self.notclientid,
                shortname='p1')
        newraw = rm.RawFile.objects.create(name='file1', producer=prod, source_md5='abcde12345',
                size=100, date=datetime.now(), claimed=False)
        trfraw = rm.RawFile.objects.create(name='filetrf', producer=prod, source_md5='defghi123',
                size=100, date=datetime.now(), claimed=False)
        doneraw = rm.RawFile.objects.create(name='filedone', producer=prod, source_md5='jklmnop123',
                size=100, date=datetime.now(), claimed=False)
        multifileraw = rm.RawFile.objects.create(name='filemulti', producer=prod, source_md5='jsldjak8',
                size=100, date=datetime.now(), claimed=False)
        trfsf = rm.StoredFile.objects.create(rawfile=trfraw, filename=trfraw.name, servershare_id=1,
                path='', md5='', checked=False, filetype_id=1)
        donesf = rm.StoredFile.objects.create(rawfile=doneraw, filename=doneraw.name, servershare_id=1,
                path='', md5='jklmnop123', checked=True, filetype_id=1)
        multisf1 = rm.StoredFile.objects.create(rawfile=multifileraw, filename=multifileraw.name, servershare_id=1,
                path='', md5='', checked=False, filetype_id=1)
        multisf2 = rm.StoredFile.objects.create(rawfile=multifileraw, filename=multifileraw.name, servershare_id=1,
                path='', md5='', checked=False, filetype_id=1)

    def test_transferstateview(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': self.clientid, 'fnids': [1, 2, 3, 99]})
        rj = resp.json()
        self.assertEqual(rj['scpfns'], [1])
        self.assertEqual(rj['waitfns'], [2])
        self.assertEqual(rj['donefns'], [3])
        self.assertEqual(rj['unknownfns'], [99])
        # check if job has been queued,
        job = jm.Job.objects.get()
        self.assertEqual(job.funcname, 'get_md5')
        self.assertEqual(job.kwargs, {'sf_id': 1, 'source_md5': 'defghi123'})
        # test all the fail HTTPs
        resp = self.cl.get(self.url)
        self.assertEqual(resp.status_code, 405)
        resp = self.cl.post(self.url, content_type='application/json', data={'hello': 'test'})
        self.assertEqual(resp.status_code, 400)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': 'wrongid', 'fnids': [1, 2, 3, 99]})
        self.assertEqual(resp.status_code, 403)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': self.notclientid, 'fnids': [1, 2, 3, 99]})
        self.assertEqual(resp.status_code, 403)
        
        # fnid 4 with multiple storedfiles -> conflict
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': self.clientid, 'fnids': [1,4]})
        self.assertEqual(resp.status_code, 409)
