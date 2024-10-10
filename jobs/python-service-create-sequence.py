from stress_testing.stress_testing import (
    SequenceRequest,
    RandomValue,
    Calc
)

import rstr


start = 0
no_devices = 1000
no_services = 10000
num_vlan = 20


intent = {
  "op": "create",
  "resource": "/python-service:python-service",
  "data": {
    "service":{
      "name": "S<<sid>>",
      "delay": "<<delay>>",
      "template": "vlans",
      "device": "r<<did>>",
      "start-vlan": "<<startvlan>>",
      "num-vlan": "<<numvlan>>",
      "str-value": rstr.letters(15)
    }
  },
  "query_parameters": {
    "no-networking": "true",
#    "commit-queue": "sync",
  }
}

parameters = {
    "sid": SequenceRequest(start),
    "did": SequenceRequest(start%no_devices, no_devices),
    "data": RandomValue(0, 4000000000),
    "delay": 0,
    "startvlan": Calc('sid', no_devices, num_vlan, 1),
    "numvlan": num_vlan,
    "concurrency": 15,
#    "requests-per-second": 8, # 0 means no limit
    "stop": no_services, # 0 means continue forever
}
