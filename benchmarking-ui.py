#!/usr/bin/env python3

from datetime import datetime
import os
from pathlib import PurePath
from random import randint
import time

from flask import Flask, request, render_template, send_file, Response,\
                  stream_with_context, jsonify
from flask_socketio import SocketIO, emit, disconnect

import ui_pb2
import ui_pb2_grpc
import grpc

app = Flask(__name__)
socketio = SocketIO(app, async_mode=None)


def notifications_task():
    print("Starting notification task")
    running = True
    while running:
        with grpc.insecure_channel('localhost:50052') as channel:
            stub = ui_pb2_grpc.UIStub(channel)
            try:
                for metric in stub.Subscribe(ui_pb2.Empty()):
                    socketio.emit('value', {
                        'ts': metric.timestamp*1000,
                        'ok': metric.ok,
                        'nok': metric.nok
                    })
            except KeyboardInterrupt:
                running = False
            except grpc._channel._InactiveRpcError:
                print("Notification subscription not available, retrying...")
                socketio.sleep(2)
            except grpc._channel._MultiThreadedRendezvous:
                print("Notification subscription not available, retrying...")
                socketio.sleep(2)
            except Exception as e:
                print("Couldn't subscribe to notifications.", e)
                running = False


def get_metrics(history=300, end_timestamp=0):
    metrics = []
    with grpc.insecure_channel('localhost:50052') as channel:
        stub = ui_pb2_grpc.UIStub(channel)
        response = stub.Get(ui_pb2.GetRequest(
            history=history, end_timestamp=end_timestamp), timeout=5)
        for m in response.metrics:
            metrics.append((m.timestamp, m.ok, m.nok))
    return metrics, response.retention
    

@app.route("/")
def r_index():
    return send_file('templates/index.html')


@socketio.on('start')
def handle_message(data):
    request_id = data.get('request_id') if isinstance(data, dict) else None
    try:
        if not isinstance(data, dict):
            raise ValueError('Expected a history request object.')
        duration = data.get('duration', data.get('windowsize', 300))
        end = data.get('end_timestamp', 0)
        for name, value, minimum, maximum in (
                ('duration', duration, 1, 4294967295 - 60),
                ('end_timestamp', end, 0, 4294967295)):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f'Invalid {name}.')
        end = min(end or int(time.time()), int(time.time()))
        # Extra samples seed the largest rolling average before the visible range.
        history = duration + 60
        metrics, retention = get_metrics(history, end)
    except (ValueError, grpc.RpcError) as error:
        app.logger.warning('Cannot load metrics: %s', error)
        emit('history_error', {'request_id': request_id,
                               'message': 'Unable to load metrics history.'})
        return
    metrics = [{'ts': m[0]*1000, 'ok': m[1], 'nok': m[2]} for m in metrics]
    emit('startdata', {'metrics': metrics, 'retention': retention,
                       'request_id': request_id,
                       'end': end * 1000})


if __name__ == "__main__":
    try:
        notif_task = socketio.start_background_task(notifications_task)
        app.run(debug=True, host='0.0.0.0', port=4000, use_reloader=False)
    except KeyboardInterrupt:
        print("Stopped")
        notif_task.stop()
