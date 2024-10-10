import asyncio
import time
import traceback
from datetime import datetime
from .restconf_api import restconf_request
from .tasks import default_task
from .restconf_api import setup, teardown


###############################################################################
#  EXECUTORS
###############################################################################
#
# Executes the requested task until the number of parameter['stop'] requests 
# have been performed. If stop is 0 (default), it will continue forever.
#
# batch_executor (currently not implemented) executes requests in batches',
# with the size of parameter['concurrency'], and waits for them to complete.
#
# sliding_window_executor executes requests using a window, of the size:
# parameter['concurrency'], and starts a new requests as soon one has completed.
# The parameter['requests-per-second'] can be used to limit the rate,
# 0 (default) means as fast a possible.
#

async def batch_executor(args, task_args, parameters, setup_func=setup,
                                teardown_func=teardown, task_func=default_task):
    results = []
    n = parameters.get('n', 1)
    n_p = parameters.get('n_p', 1)
    while n > 0:  # Execute requests in batches of n_p in parellel.
        if n < n_p:
            n_p = n
        await setup_func(task_args)
        st = time.monotonic()
        tasks = [asyncio.create_task(task_func(args, parameters, **task_args))
                 for p in range(0, n_p)]
        results += await asyncio.gather(*tasks)
        await teardown_func(task_args)
        parameters.update_batch()
        n -= n_p
    elapsed = time.monotonic()-st
    return elapsed, results


async def sliding_window_executor(args, task_args, parameters,
                              global_parameters=None, last=None, want_results=True, 
                              setup_func=setup, teardown_func=teardown,
                              task_func=default_task, result_queue=None, request_cb=None):
    if setup_func is not None:
        await setup_func(task_args)
    try:
        tasks = set()

        parameters['requests-count'] = 0
        parameters['task-wait-dept'] = 0
        parameters['ok'] = 0
        parameters['nok'] = 0
        parameters['exc'] = 0
        req_count = 0

        task_func = task_func or default_task
        start = time.monotonic()

        # Start initial concurrency number of tasks
        stop = parameters.get('stop', 0)
        rps = parameters.get('requests-per-second', 0)
        concurrency = parameters.get('concurrency', 1)
        for _ in range(0, concurrency):
            if req_count%concurrency == 0:
                parameters.update_batch() # Update batched parameters
                # TODO: Is this guaranteed to be executed directly in relation
                #       to the call to task_func below?
            tasks.add(asyncio.create_task(task_func(args, parameters, **task_args)))
            if rps > 0:
                await asyncio.sleep(1/(rps/concurrency))
            req_count += 1
            if stop > 0 and req_count >= stop:
                break
        # TODO: Must find a better way to handle close_flag
        close_flag = 0
        results = []
        n = 0
        new_task_delays = []
        while not close_flag and len(tasks) > 0:
            done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            stop = parameters.get('stop', 0)
            rps = parameters.get('requests-per-second', 0)
            add_to_metrics = parameters.get('add_to_metrics', False)
            concurrency = parameters.get('concurrency', 1)
            for d in done:
                if global_parameters:
                    global_parameters['requests-count'] += 1
                result = await d
                if request_cb:
                    request_cb(result)
                if want_results:
                    results.append(result)
                _rid, rstatus, _rcode, _rresult, rtime = result
                if last:
                    last['result'] = last_result = (datetime.now().isoformat(), result)
                    if rstatus == 'ok':
                        parameters['ok'] += 1
                        last['success'] = last_result
                    elif rstatus == 'nok':
                        parameters['nok'] += 1
                        last['error'] = last_result
                    else:
                        parameters['exc'] += 1
                        last_exc = last_result
                if add_to_metrics and result_queue is not None:
                    # Push results to metrics_handler
                    await result_queue.put((time.time(), result))

                d = 1/(rps/concurrency)-rtime if rps>0 else 0
                if d < 0:
                    # This means that concurrency may need to be increased
                    parameters['task-wait-dept'] -= d
                new_task_delays.append(d)
            # Start tasks in available slots (if any)
            for _ in range(concurrency-len(tasks)):
                if stop == 0 or req_count < stop:
                    d = new_task_delays.pop(0) if new_task_delays else 1/(rps/concurrency)
                    async def new_task():
                        if d > 0:
                            await asyncio.sleep(d)
                        return await task_func(args, parameters, **task_args)
                    if req_count%concurrency == 0:
                        parameters.update_batch() # Update batched parameters
                        # TODO: Is this guaranteed to be executed directly in relation
                        #       to the call to task_func below?
                    tasks.add(asyncio.create_task(new_task()))
                    req_count += 1
            if global_parameters:
                close_flag = global_parameters['close_flag']
    except asyncio.CancelledError:
        # TODO: More graceful shutdown and collect results?
        pass
    except Exception as e:
        print("EXCEPTION", e)
        # Print traceback
        print(traceback.format_exc())
        raise e
    finally:
        elapsed = time.monotonic()-start
        for t in tasks:
            t.cancel()
        if teardown_func is not None:
            await teardown_func(task_args)
    return elapsed, results


async def single_request(args, task_args, parameters, setup_func=setup, 
                         teardown_func=teardown, task=default_task):
    # Setup connection pool
    await setup_func(task_args)
    result = await task(args, parameters, **task_args)
    # Cleanup connection pool
    await teardown_func(args)
    return result
