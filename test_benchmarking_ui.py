import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    'benchmarking_ui', Path(__file__).with_name('benchmarking-ui.py'))
ui = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ui)


class HistoryRequestTest(unittest.TestCase):
    def setUp(self):
        self.client = ui.socketio.test_client(ui.app)

    def tearDown(self):
        self.client.disconnect()

    def test_live_request_includes_average_context_not_full_retention(self):
        with patch.object(ui.time, 'time', return_value=100000), \
                patch.object(ui, 'get_metrics', return_value=([(100000, 3, 0)], 86400)) as get:
            self.client.emit('start', {'duration': 302, 'request_id': 1})
        get.assert_called_once_with(362, 100000)
        event = self.client.get_received()[0]
        self.assertEqual('startdata', event['name'])
        self.assertEqual(1, event['args'][0]['request_id'])
        self.assertEqual(86400, event['args'][0]['retention'])

    def test_pan_requests_bounded_historical_range(self):
        with patch.object(ui.time, 'time', return_value=100000), \
                patch.object(ui, 'get_metrics', return_value=([], 86400)) as get:
            self.client.emit('start', {
                'duration': 300, 'end_timestamp': 99000, 'request_id': 2})
        get.assert_called_once_with(360, 99000)

    def test_invalid_requests_report_errors_without_querying(self):
        for request in (None, {'duration': 0}, {'duration': True},
                        {'duration': '300'}, {'end_timestamp': -1}):
            with patch.object(ui, 'get_metrics') as get:
                self.client.emit('start', request)
            get.assert_not_called()
            self.assertEqual('history_error', self.client.get_received()[0]['name'])

    def test_rpc_error_is_visible(self):
        with patch.object(ui, 'get_metrics', side_effect=ui.grpc.RpcError('unavailable')):
            self.client.emit('start', {'duration': 300, 'request_id': 3})
        event = self.client.get_received()[0]
        self.assertEqual('history_error', event['name'])
        self.assertEqual(3, event['args'][0]['request_id'])


if __name__ == '__main__':
    unittest.main()
