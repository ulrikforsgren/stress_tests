import asyncio
import math
import time

from stress_testing.parameters import SequenceRequest, RandomValue

async def job(args, global_parameters, cmd_params={}, result_queue=None):
    global_parameters.update({
        "id": RandomValue(0, 4000000000),
        "value": SequenceRequest(0),
        "delay": 1000,
        "requests-count": 0,
        "period": 60,
    })
    global_parameters.set(cmd_params)
    try:
        while True:
            global_parameters['requests-count'] += 1
            await asyncio.sleep(global_parameters['delay']/1000)
            if global_parameters['add_to_metrics']:
                n = int((math.sin(
                    global_parameters['requests-count']*2*math.pi/global_parameters['period'])+1)*1000)
                for _ in range(int(n)):
                    await result_queue.put((time.time(), (
                        global_parameters['id'],
                        'ok',
                        200,
                        None
                    )))
                for _ in range(2000-n):
                    await result_queue.put((time.time(), (
                        global_parameters['id'],
                        'nok',
                        200,
                        None
                    )))
    except asyncio.CancelledError:
        pass