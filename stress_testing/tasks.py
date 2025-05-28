import json
import time
from .restconf_api import restconf_request
from .parameters import format_parameters


###############################################################################
#  TASKS
###############################################################################
#
##### Default Task
#
# parameters (dict) has following keys:
# - concurrency: number of concurrent requests (int) (optional)
# - stop: stop after number of requests (int) (optional)
# - requests-per-second: number of requests per second (int) (optional)
#
# task_args (dict) keys:
# - host: host to connect to (ip:port)
# - op: operation (create, read, update, delete, action)
# - resource: resource path
# - data: request payload (dict/string) (optional)
# - resource_type: RESTCONF resource type (data, operations) (optional) 
# - query_parameters: RESTCONF query parameters (dict) (optional)
#

async def default_task(args, parameters, client=None,
                       host='', op='', resource='', data='',
                       resource_type='data', query_parameters=None):
    if isinstance(data, dict):
        data = json.dumps(data)
    # Update parameters for this request
    parameters.update_request()
    # Substitute request parameters 
    resource = format_parameters(parameters, resource)
    data = format_parameters(parameters, data)
    # Schedule request and measure execution time
    st = time.monotonic()
    resp = await restconf_request(args,
                                  client,
                                  host,
                                  op,
                                  resource,
                                  data,
                                  resource_type,
                                  query_parameters)
    elapsed = time.monotonic()-st
    return (*resp, elapsed)