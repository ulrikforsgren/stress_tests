import asyncio
import math
import time

from stress_testing.parameters import SequenceRequest, RandomValue

async def job(args, ctx, rq, data, extra_params={}):
    ctx.update({
        "id": RandomValue(0, 4000000000),
        "value": SequenceRequest(0),
        "delay": 1000,
        "requests-count": 0,
        "period": 60,
    })
    ctx.set(extra_params)
    try:
        while True:
            ctx['requests-count'] += 1
            await asyncio.sleep(ctx['delay']/1000)
            if ctx['add_to_metrics']:
                n = int((math.sin(
                    ctx['requests-count']*2*math.pi/ctx['period'])+1)*1000)
                for _ in range(int(n)):
                    await rq.put((time.time(), (
                        ctx['id'],
                        'ok',
                        200,
                        None
                    )))
                for _ in range(2000-n):
                    await rq.put((time.time(), (
                        ctx['id'],
                        'nok',
                        200,
                        None
                    )))
    except asyncio.CancelledError:
        pass