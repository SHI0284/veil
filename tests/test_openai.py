import io
import json
import unittest
import urllib.error
from unittest.mock import Mock, patch
from veil_app.openai_client import AISettings, OpenAIClient, ProviderError
from veil_app.web import create_app


class OpenAITests(unittest.TestCase):
    def setUp(self):
        with patch.dict('os.environ', {}, clear=True):
            self.settings = AISettings()

    def client(self, transport):
        self.settings.update('sk-test-only', 'gpt-4.1-mini')
        return OpenAIClient(self.settings, transport)

    def test_wire_contract_and_text_extraction(self):
        transport = Mock(return_value=io.BytesIO(json.dumps({'status':'completed', 'output':[
            {'type':'reasoning'}, {'type':'message','content':[{'type':'output_text','text':'답변'}]}]}).encode()))
        self.assertEqual(self.client(transport).request('[보호정보] 검토'), '답변')
        req = transport.call_args.args[0]
        data = json.loads(req.data)
        self.assertEqual(req.full_url, 'https://api.openai.com/v1/responses')
        self.assertEqual(data['input'], '[보호정보] 검토')
        self.assertFalse(data['store'])
        self.assertNotIn('previous_response_id', data)
        self.assertEqual(transport.call_args.kwargs['timeout'], 45)

    def test_missing_key_fails_before_network(self):
        transport = Mock()
        with self.assertRaises(ProviderError):
            OpenAIClient(self.settings, transport).request('공개 질문')
        transport.assert_not_called()

    def test_errors_do_not_echo_upstream_secrets(self):
        for code in (400, 401, 403, 404, 429, 500):
            transport = Mock(side_effect=urllib.error.HTTPError('url',code,'sk-secret private prompt',{},None))
            with self.assertRaises(ProviderError) as raised:
                self.client(transport).request('private prompt')
            self.assertNotIn('sk-secret', str(raised.exception))
            self.assertNotIn('private prompt', str(raised.exception))
            self.assertEqual(raised.exception.uncertain, code >= 500)

    def test_timeout_and_incomplete_are_uncertain(self):
        for transport in (Mock(side_effect=TimeoutError()), Mock(return_value=io.BytesIO(b'{"status":"incomplete"}')), Mock(return_value=io.BytesIO(b'{"status":"completed","output":null}'))):
            with self.assertRaises(ProviderError) as raised:
                self.client(transport).request('test')
            self.assertTrue(raised.exception.uncertain)
            self.assertEqual(transport.call_count, 1)

    def test_key_not_in_public_settings_and_validation_atomic(self):
        self.settings.update('sk-test-only', 'gpt-4.1-mini')
        with self.assertRaises(ValueError):
            self.settings.update('sk-replacement', 'bad model\n')
        self.assertEqual(self.settings._key, 'sk-test-only')
        self.assertNotIn('sk-test-only', json.dumps(self.settings.public()))


class LiveAdapterWebTests(unittest.TestCase):
    def setUp(self):
        with patch.dict('os.environ', {}, clear=True):
            self.app = create_app(':memory:')
        self.client = self.app.test_client()
        self.csrf = self.client.get('/api/session').json['csrf']

    def tearDown(self):
        self.app.extensions['veil_repository'].close()

    def post(self, path, data):
        return self.client.post('/api/' + path, json=data, headers={'X-CSRF-Token':self.csrf})

    def login(self, user='researcher'):
        result = self.post('login', {'username':user,'password':'veil1234!'})
        self.csrf = result.json['csrf']
        return result.json

    def analyze(self, content):
        p = self.post('analyze', {'content':content}).json['prompt']
        return {'prompt_id':p['id'], 'result_id':p['result']['id'], 'content':p['content']}

    def agent(self):
        return next(iter(self.app.extensions['veil_states'].values()))['agent']

    def test_missing_key_preserves_input_without_fake_answer(self):
        self.assertFalse(self.login()['ai']['is_demo'])
        request = self.analyze('공개된 논문을 요약해줘')
        result = self.post('send', request)
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.json['state']['prompt']['content'], request['content'])
        self.assertEqual(result.json['state']['messages'], [])

    def test_manager_only_settings_and_no_key_response(self):
        self.login()
        self.assertEqual(self.post('ai-settings', {'api_key':'sk-test-only','model':'gpt-4.1-mini'}).status_code,403)
        self.login('manager')
        result = self.post('ai-settings', {'api_key':'sk-test-only','model':'gpt-4.1-mini'})
        self.assertTrue(result.json['ai']['configured'])
        self.assertNotIn('sk-test-only', result.get_data(as_text=True))
        self.login()
        self.assertTrue(self.client.get('/api/session').json['ai']['configured'])

    def test_timeout_blocks_repeated_send_and_reanalysis(self):
        self.login()
        self.app.extensions['veil_ai_settings'].update('sk-test-only','gpt-4.1-mini')
        transport = Mock(side_effect=TimeoutError())
        self.agent().gateway.client.transport = transport
        request = self.analyze('공개 자료 요약')
        result = self.post('send',request)
        self.assertEqual(result.json['state']['prompt']['status'], 'SEND_UNKNOWN')
        self.assertEqual(self.post('send',request).status_code,400)
        self.assertEqual(self.post('analyze',{'content':request['content']}).status_code,400)
        self.assertEqual(transport.call_count,1)

    def test_blocked_input_never_reaches_provider(self):
        self.login()
        transport = Mock()
        self.agent().gateway.client.transport = transport
        request = self.analyze('보안과제 핵심기술')
        self.assertEqual(self.post('send',request).status_code,400)
        transport.assert_not_called()

    def test_transformed_prompt_only_and_real_response_route(self):
        self.login()
        self.app.extensions['veil_ai_settings'].update('sk-test-only','gpt-4.1-mini')
        transport = Mock(return_value=io.BytesIO(b'{"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":"API response"}]}]}'))
        self.agent().gateway.client.transport = transport
        request = self.analyze('010-1234-5678 연락처 검토')
        preview = self.post('preview',request).json
        p = self.post('approve',dict(request,token=preview['token'])).json['prompt']
        response = self.post('send',{'prompt_id':p['id'],'result_id':p['result']['id'],'content':p['content']})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['messages'][-1]['content'],'API response')
        wire = json.loads(transport.call_args.args[0].data)
        self.assertNotIn('010-1234-5678', json.dumps(wire))
        self.assertIn('[보호정보]', wire['input'])
