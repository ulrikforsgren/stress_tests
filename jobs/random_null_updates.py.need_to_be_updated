from stress_testing.stress_testing import SequenceRequest, RandomValue, \
                                          RandomString, ContextValue
import json

def read_services():
    services = {}
    with open('services.json') as f:
        service_list = json.load(f)['data']['python-service:python-service']['service']
        for s in service_list:
            name = s['name']
            del s['name']
            services[name] = s
    return services

SERVICES = read_services()


DATA = \
{
  "op": "update",
  "url": "/python-service:python-service/service=S<<id>>",
  "data": {
    "service":{
      "str-value": "<<ctxvalue>>"
    }
  },
  "parameters": {
    "id": RandomValue(0, 100000),
    "rndstr": RandomString(15),
    "ctxvalue": ContextValue(SERVICES, 'S<<id>>', 'str-value'),
    "delay": 0,
    "numvlan": 800,
    "concurrency": 40,
    "stop": 0,  # Continue forever
  },
  "params": {"no-networking": "true"}
}
