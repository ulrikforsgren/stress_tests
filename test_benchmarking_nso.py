import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name('benchmarking-nso.py')
SPEC = importlib.util.spec_from_file_location('benchmarking_nso', MODULE_PATH)
benchmarking_nso = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmarking_nso)
MetricsStore = benchmarking_nso.MetricsStore


class MetricsStoreTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / 'metrics.db'
        self.store = MetricsStore(self.database)

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_metrics_persist_across_connections(self):
        self.store.record(100, 12, 3)
        self.store.close()

        self.store = MetricsStore(self.database)

        self.assertEqual([(100, 12, 3)], self.store.get())

    def test_get_filters_by_elapsed_time(self):
        self.store.record(100, 1, 0)
        self.store.record(101, 2, 1)
        self.store.record(102, 3, 2)

        self.assertEqual(
            [(101, 2, 1), (102, 3, 2)],
            self.store.get(history=2, now=102),
        )

    def test_record_replaces_a_duplicate_timestamp(self):
        self.store.record(100, 1, 2)
        self.store.record(100, 3, 4)

        self.assertEqual([(100, 3, 4)], self.store.get())

    def test_get_historical_range_excludes_newer_metrics(self):
        for timestamp in range(100, 105):
            self.store.record(timestamp, timestamp, 0)

        self.assertEqual(
            [(101, 101, 0), (102, 102, 0)],
            self.store.get(history=2, end_timestamp=102),
        )
        self.assertEqual(
            [(100, 100, 0), (101, 101, 0), (102, 102, 0)],
            self.store.get(end_timestamp=102),
        )

    def test_prune_removes_expired_metrics(self):
        self.store.record(100, 1, 0)
        self.store.record(101, 2, 0)
        self.store.record(102, 3, 0)

        removed = self.store.prune(retention=2, now=102)

        self.assertEqual(1, removed)
        self.assertEqual([(101, 2, 0), (102, 3, 0)], self.store.get())


class HistoryServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_historical_range_over_grpc(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MetricsStore(Path(directory) / 'metrics.db')
            server = benchmarking_nso.grpc.aio.server()
            try:
                now = int(benchmarking_nso.time.time())
                for ts in range(now - 5, now):
                    store.record(ts, ts, 0)
                benchmarking_nso.ui_pb2_grpc.add_UIServicer_to_server(
                    benchmarking_nso.UIServicer(SimpleNamespace(history=10), store),
                    server)
                port = server.add_insecure_port('127.0.0.1:0')
                await server.start()
                async with benchmarking_nso.grpc.aio.insecure_channel(
                        f'127.0.0.1:{port}') as channel:
                    stub = benchmarking_nso.ui_pb2_grpc.UIStub(channel)
                    response = await stub.Get(
                        benchmarking_nso.ui_pb2.GetRequest(
                            history=2, end_timestamp=now - 3), timeout=5)
                self.assertEqual([now - 4, now - 3],
                                 [m.timestamp for m in response.metrics])
            finally:
                await server.stop(0)
                store.close()

    async def test_day_retention_only_returns_requested_window(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MetricsStore(Path(directory) / 'metrics.db')
            try:
                with store.connection:
                    store.connection.executemany(
                        'INSERT INTO metrics VALUES (?, ?, ?)',
                        ((ts, ts % 100, 0) for ts in range(1, 86401)))
                service = benchmarking_nso.UIServicer(
                    SimpleNamespace(history=86400), store)
                with patch.object(benchmarking_nso.time, 'time', return_value=86400):
                    response = await service.Get(
                        benchmarking_nso.ui_pb2.GetRequest(history=362), None)
                self.assertEqual(362, len(response.metrics))
                self.assertEqual(86039, response.metrics[0].timestamp)
                self.assertEqual(86400, response.retention)
            finally:
                store.close()

    async def test_old_ranges_are_clipped_to_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MetricsStore(Path(directory) / 'metrics.db')
            try:
                for ts in range(1, 11):
                    store.record(ts, ts, 0)
                service = benchmarking_nso.UIServicer(SimpleNamespace(history=5), store)
                with patch.object(benchmarking_nso.time, 'time', return_value=10):
                    clipped = await service.Get(
                        benchmarking_nso.ui_pb2.GetRequest(
                            history=10, end_timestamp=8), None)
                    expired = await service.Get(
                        benchmarking_nso.ui_pb2.GetRequest(
                            history=2, end_timestamp=4), None)
                    future = await service.Get(
                        benchmarking_nso.ui_pb2.GetRequest(
                            history=2, end_timestamp=100), None)
                self.assertEqual([6, 7, 8], [m.timestamp for m in clipped.metrics])
                self.assertEqual([], list(expired.metrics))
                self.assertEqual([9, 10], [m.timestamp for m in future.metrics])
            finally:
                store.close()


if __name__ == '__main__':
    unittest.main()
