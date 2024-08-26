import json
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
from app import app, query_time, get_secret, get_ip

class TestApp(unittest.TestCase):

    @patch('app.requests.get')
    def test_query_time_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({'datetime': '2023-01-01T00:00:00Z'})
        mock_get.return_value = mock_response

        result = query_time()
        self.assertEqual(result, '2023-01-01T00:00:00Z')

    @patch('app.requests.get')
    def test_query_time_failure(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = query_time()
        self.assertEqual(result, 'Unavailable')

    @patch('app.requests.get', side_effect=Exception('API Error'))
    def test_query_time_exception(self, mock_get):
        result = query_time()
        self.assertEqual(result, 'Unavailable')

    @patch('app.os.getenv')
    @patch('app.SecretClient')
    @patch('app.DefaultAzureCredential')
    def test_get_secret_success(self, mock_credential, mock_secret_client, mock_getenv):
        mock_getenv.side_effect = lambda key: 'test_value' if key in ['KEY_VAULT_NAME', 'KEY_VAULT_SECRET_NAME', 'MSI_CLIENT_ID'] else None
        mock_secret_instance = MagicMock()
        mock_secret_instance.get_secret.return_value.value = 'secret_value'
        mock_secret_client.return_value = mock_secret_instance

        result = get_secret()
        self.assertEqual(result, 'secret_value')

    @patch('app.os.getenv')
    @patch('app.DefaultAzureCredential', side_effect=Exception('Token Error'))
    def test_get_secret_token_failure(self, mock_credential, mock_getenv):
        mock_getenv.side_effect = lambda key: 'test_value' if key in ['KEY_VAULT_NAME', 'KEY_VAULT_SECRET_NAME', 'MSI_CLIENT_ID'] else None

        with self.assertRaises(Exception) as context:
            get_secret()
        self.assertIn('Failed to obtain access token', str(context.exception))

    @patch('app.os.getenv')
    @patch('app.SecretClient', side_effect=Exception('Secret Error'))
    @patch('app.DefaultAzureCredential')
    def test_get_secret_retrieval_failure(self, mock_credential, mock_secret_client, mock_getenv):
        mock_getenv.side_effect = lambda key: 'test_value' if key in ['KEY_VAULT_NAME', 'KEY_VAULT_SECRET_NAME', 'MSI_CLIENT_ID'] else None

        with self.assertRaises(Exception) as context:
            get_secret()
        self.assertIn('Failed to get secret', str(context.exception))

    def test_get_ip_with_x_forwarded_for(self):
        mock_request = MagicMock()
        mock_request.headers = {'X-Forwarded-For': '1.2.3.4'}
        mock_request.remote_addr = '5.6.7.8'

        result = get_ip(mock_request)
        self.assertEqual(result, '5.6.7.8 and X-Forwarded-For header value of 1.2.3.4')

    def test_get_ip_without_x_forwarded_for(self):
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.remote_addr = '5.6.7.8'

        result = get_ip(mock_request)
        self.assertEqual(result, '5.6.7.8')

    @patch('app.get_ip')
    @patch('app.get_secret')
    @patch('app.query_time')
    def test_index_route(self, mock_query_time, mock_get_secret, mock_get_ip):
        mock_get_ip.return_value = '5.6.7.8'
        mock_get_secret.return_value = 'secret_value'
        mock_query_time.return_value = '2023-01-01T00:00:00Z'

        with app.test_client() as client:
            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'secret_value', response.data)
            self.assertIn(b'2023-01-01T00:00:00Z', response.data)
            self.assertIn(b'5.6.7.8', response.data)

if __name__ == '__main__':
    unittest.main()