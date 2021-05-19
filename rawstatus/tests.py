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
        ss = rm.ServerShare.objects.create(name='testserevr', uri='test.test', share='/home/test')
        ft = rm.StoredFileType.objects.create(name='testft', filetype='tst')
        prod = rm.Producer.objects.create(name='prod1', client_id=self.clientid, shortname='p1')
        otherprod = rm.Producer.objects.create(name='otherprod1', client_id=self.notclientid,
                shortname='p1')
        self.newraw = rm.RawFile.objects.create(name='file1', producer=prod, source_md5='abcde12345',
                size=100, date=datetime.now(), claimed=False)
        self.trfraw = rm.RawFile.objects.create(name='filetrf', producer=prod, source_md5='defghi123',
                size=100, date=datetime.now(), claimed=False)
        self.doneraw = rm.RawFile.objects.create(name='filedone', producer=prod, source_md5='jklmnop123',
                size=100, date=datetime.now(), claimed=False)
        self.multifileraw = rm.RawFile.objects.create(name='filemulti', producer=prod, source_md5='jsldjak8',
                size=100, date=datetime.now(), claimed=False)
        self.trfsf = rm.StoredFile.objects.create(rawfile=self.trfraw, filename=self.trfraw.name, servershare_id=ss.id,
                path='', md5='', checked=False, filetype_id=ft.id)
        self.donesf = rm.StoredFile.objects.create(rawfile=self.doneraw, filename=self.doneraw.name, servershare_id=ss.id,
                path='', md5='jklmnop123', checked=True, filetype_id=ft.id)
        multisf1 = rm.StoredFile.objects.create(rawfile=self.multifileraw, filename=self.multifileraw.name, servershare_id=ss.id,
                path='', md5='', checked=False, filetype_id=ft.id)
        multisf2 = rm.StoredFile.objects.create(rawfile=self.multifileraw, filename=self.multifileraw.name, servershare_id=ss.id,
                path='', md5='', checked=False, filetype_id=ft.id)

    def test_transferstate_done(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': self.clientid, 'fnid': self.doneraw.id})
        rj = resp.json()
        self.assertEqual(rj['transferstate'], 'done')

    def test_transferstate_scp(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': self.clientid, 'fnid': self.newraw.id})
        rj = resp.json()
        self.assertEqual(rj['transferstate'], 'transfer')

    def test_transferstate_wait(self):
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': self.clientid, 'fnid': self.trfraw.id})
        rj = resp.json()
        self.assertEqual(rj['transferstate'], 'wait')
        job = jm.Job.objects.get()
        self.assertEqual(job.funcname, 'get_md5')
        self.assertEqual(job.kwargs, {'sf_id': self.trfsf.id, 'source_md5': 'defghi123'})

    def test_failing_transferstate(self):
        # test all the fail HTTPs
        resp = self.cl.get(self.url)
        self.assertEqual(resp.status_code, 405)
        resp = self.cl.post(self.url, content_type='application/json', data={'hello': 'test'})
        self.assertEqual(resp.status_code, 400)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': 'wrongid', 'fnid': 1})
        self.assertEqual(resp.status_code, 403)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': self.clientid, 'fnid': 99})
        self.assertEqual(resp.status_code, 404)
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': self.notclientid, 'fnid': 1})
        self.assertEqual(resp.status_code, 403)
        
        # fnid 4 with multiple storedfiles -> conflict
        resp = self.cl.post(self.url, content_type='application/json',
                data={'client_id': self.clientid, 'fnid': 4})
        self.assertEqual(resp.status_code, 409)
