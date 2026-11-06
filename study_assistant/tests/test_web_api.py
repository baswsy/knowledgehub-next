import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import storage
from web_api import app

class WebAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patches=[patch.object(storage,'BASE',Path(self.tmp.name)),patch.dict(os.environ,{'STUDY_ACCESS_PASSWORD':'test-only'})]
        for p in self.patches:p.start()
        self.client=TestClient(app);self.auth={'Authorization':'Bearer test-only'}
    def tearDown(self):
        for p in self.patches:p.stop()
        self.tmp.cleanup()
    def test_auth_and_workspace(self):
        self.assertEqual(self.client.get('/health').status_code,200)
        self.assertEqual(self.client.get('/api/workspace').status_code,401)
        self.assertEqual(self.client.get('/api/workspace',headers=self.auth).json()['notes'],[])
    def test_create_edit_delete_note(self):
        r=self.client.post('/api/notes',headers=self.auth,json={'title':'课程','content':'RAG知识'})
        self.assertEqual(r.status_code,200);source=r.json()['source']
        self.client.post('/api/notes',headers=self.auth,json={'title':'课程修改','content':'新内容','source':source})
        rows=self.client.get('/api/workspace',headers=self.auth).json()['notes']
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['title'],'课程修改')
        self.assertEqual(self.client.delete('/api/notes/'+source,headers=self.auth).status_code,200)
        self.assertEqual(self.client.get('/api/workspace',headers=self.auth).json()['notes'],[])
    def test_memory_and_favorite(self):
        self.client.post('/api/memory',headers=self.auth,json={'content':'准备面试'})
        self.client.post('/api/favorites',headers=self.auth,json={'title':'视频','url':'https://www.bilibili.com/video/BV1234567890'})
        data=self.client.get('/api/workspace',headers=self.auth).json()
        self.assertEqual(data['memory'],'准备面试');self.assertEqual(len(data['favorites']),1)
    def test_cors_preflight(self):
        response=self.client.options('/api/workspace',headers={'Origin':'http://localhost:8080','Access-Control-Request-Method':'GET','Access-Control-Request-Headers':'authorization'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['access-control-allow-origin'],'http://localhost:8080')
