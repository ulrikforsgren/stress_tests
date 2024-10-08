from stress_testing.stress_testing import SequenceRequest, RandomValue

start = 0
stop = 10000 # 0 means continue forever
no_devices = 1000
no_services = 1000
num_vlan = 20

DATA = \
{
  "op": "update",
  "resource": "/python-service:python-service/service=S<<sid>>",
  "data": {
    "service":{
      "delay": "<<delay>>",
      "num-vlan": 0,
      "str-value": "<<data>>",
    }
  },
  "parameters": {
    "sid": SequenceRequest(start, wrap=no_services),
    "data": RandomValue(0, 4000000000),
    "delay": 0,
    "concurrency": 15,
    "stop": stop, # 0 means continue forever
  },
  "query_parameters": {
    "no-networking": "true",
#    "commit-queue": "sync",
  }
}