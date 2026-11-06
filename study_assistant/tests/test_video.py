import unittest
import json
from video_content import identify,parse_subtitle,render
class VideoTests(unittest.TestCase):
    def test_url_scope_and_part(self):
        self.assertEqual(identify('https://www.bilibili.com/video/BV1234567890?p=2'),('BV1234567890',2))
        for url in ['http://localhost/','https://bilibili.com.evil/video/BV1234567890','https://www.bilibili.com/video/BV1234567890?p=0']:
            with self.assertRaises(ValueError):identify(url)
    def test_srt_and_vtt(self):
        for text in ['1\n00:00:01,000 --> 00:00:03,000\n你好\n\n','WEBVTT\n\n00:01.000 --> 00:03.000\n你好\n\n']:
            self.assertEqual(parse_subtitle('a.srt',text.encode()),[(1,3,'你好')])
    def test_json_and_provenance(self):
        parts=parse_subtitle('a.json',json.dumps({'body':[{'from':2,'to':4,'content':'内容'}]}).encode())
        self.assertIn('00:00:02',render(parts,'https://www.bilibili.com/video/BV1234567890','用户上传'))
        with self.assertRaises(ValueError):parse_subtitle('a.json',b'{"body":[{"from":5,"to":2,"content":"bad"}]}')
    def test_empty_and_oversize(self):
        for content in [b'empty',b'x'*(5*1024*1024+1)]:
            with self.assertRaises(ValueError):parse_subtitle('a.srt',content)
