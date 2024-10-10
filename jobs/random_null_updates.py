from stress_testing.parameters import (
    RandomValue,
    RandomString,
    LookupValue
)

import json

stop = 0
no_vlan = 1


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


intent = {
  "op": "update",
  "url": "/python-service:python-service/service=S<<id>>",
  "data": {
    "service":{
      "str-value": "<<ctxvalue>>"
    }
  },
  "query_parameters": {
      "no-networking": "true"
  }
}

parameters = {
    "id": RandomValue(0, 100000),
    "rndstr": RandomString(15),
    "ctxvalue": LookupValue(SERVICES, 'S<<id>>', 'str-value'),
    "delay": 0,
    "numvlan": no_vlan,
    "concurrency": 40,
    "stop": stop,  # Continue forever
}
