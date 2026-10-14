"""Persistence and gRPC API shared by the benchmarking UI backends."""

import asyncio
import sqlite3
import time

import grpc
import ui_pb2
import ui_pb2_grpc


class MetricsStore:
    def __init__(self, path):
        self.connection = sqlite3.connect(path, timeout=5)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('PRAGMA synchronous=NORMAL')
        self.connection.execute('PRAGMA busy_timeout=5000')
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                timestamp INTEGER PRIMARY KEY,
                ok INTEGER NOT NULL,
                nok INTEGER NOT NULL
            )
        ''')
        self.connection.commit()

    def record(self, timestamp, ok, nok):
        metric = (int(timestamp), ok, nok)
        with self.connection:
            self.connection.execute('''
                INSERT INTO metrics(timestamp, ok, nok) VALUES (?, ?, ?)
                ON CONFLICT(timestamp) DO UPDATE SET
                    ok=excluded.ok,
                    nok=excluded.nok
            ''', metric)
        return metric

    def get(self, history=0, now=None, end_timestamp=None):
        if end_timestamp is not None:
            cutoff = end_timestamp - history + 1 if history else 0
            cursor = self.connection.execute('''
                SELECT timestamp, ok, nok FROM metrics
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp
            ''', (cutoff, end_timestamp))
            return cursor.fetchall()
        if history:
            now = int(time.time() if now is None else now)
            cutoff = now - history + 1
            cursor = self.connection.execute('''
                SELECT timestamp, ok, nok FROM metrics
                WHERE timestamp >= ?
                ORDER BY timestamp
            ''', (cutoff,))
        else:
            cursor = self.connection.execute('''
                SELECT timestamp, ok, nok FROM metrics
                ORDER BY timestamp
            ''')
        return cursor.fetchall()

    def prune(self, retention, now=None):
        now = int(time.time() if now is None else now)
        cutoff = now - retention + 1
        with self.connection:
            cursor = self.connection.execute(
                'DELETE FROM metrics WHERE timestamp < ?', (cutoff,))
        return cursor.rowcount

    def close(self):
        self.connection.close()


class ProdCons:
    def __init__(self):
        self.consumers = []

    async def emit(self, notif):
        for consumer in self.consumers:
            await consumer.put(notif)

    def subscribe(self):
        queue = asyncio.Queue()
        self.consumers.append(queue)
        return queue

    def unsubscribe(self, queue):
        if queue in self.consumers:
            self.consumers.remove(queue)


class UIServicer(ui_pb2_grpc.UIServicer):
    def __init__(self, args, metrics_store):
        self.args = args
        self.metrics_store = metrics_store

    async def Get(self, request, unused_context):
        response = ui_pb2.GetResponse(retention=self.args.history)
        now = int(time.time())
        end = min(request.end_timestamp or now, now)
        duration = min(request.history or self.args.history,
                       self.args.history, end - (now - self.args.history))
        history = (self.metrics_store.get(duration, end_timestamp=end)
                   if duration > 0 else [])
        for timestamp, ok, nok in history:
            response.metrics.append(ui_pb2.Metric(
                timestamp=int(timestamp), ok=ok, nok=nok))
        return response

    async def Subscribe(self, request, unused_context):
        queue = notifications.subscribe()
        try:
            while True:
                yield await queue.get()
        except asyncio.CancelledError:
            raise
        finally:
            notifications.unsubscribe(queue)


notifications = ProdCons()
