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
from grpc._channel import _InactiveRpcError

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


def get_metrics(history=300):
    metrics = []
    try:
        with grpc.insecure_channel('localhost:50052') as channel:
            stub = ui_pb2_grpc.UIStub(channel)
            response = stub.Get(ui_pb2.GetRequest(history=history))
            for m in response.metrics:
                metrics.append((m.timestamp, m.ok, m.nok))
        return metrics
    except _InactiveRpcError:
        return []
    

@app.route("/")
def r_index():
    return send_file('templates/index.html')


@socketio.on('start')
def handle_message(data):
    global metrics
    print(f'start: received message: {data}')
    print('Time difference client-server (ms):', data['timestamp']-time.time()*1000)
    windowsize = data['windowsize']
    metrics = get_metrics(windowsize)
    data = [{ 'ts': m[0]*1000, 'ok': m[1], 'nok': m[2]} for m in metrics]
    emit('startdata', data)


if __name__ == "__main__":
    try:
        notif_task = socketio.start_background_task(notifications_task)
        app.run(debug=True, host='0.0.0.0', port=4000, use_reloader=False)
    except KeyboardInterrupt:
        print("Stopped")
        notif_task.stop()
