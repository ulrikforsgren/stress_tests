from stress_testing.stress_testing import SequenceRequest, RandomValueRequest, RandomString, Calc

start=0
stop=0 # 0 means continue forever
no_services=1000
no_devices=1000
no_vlan=20

DATA = \
{
  "op": "update",
  "resource": "/python-service:python-service/service=S<<sid>>",
  "data": {
    "service":{
      "delay": "<<delay>>",
      "start-vlan": "<<startvlan>>",
      "str-value": "<<rndstr>>",
    }
  },
  "parameters": {
    "sid": RandomValueRequest(0, no_services),
    "rndstr": RandomString(15),
    "delay": 0,
    "startvlan": Calc('sid', no_devices, no_vlan, 1),
    "numvlan": no_vlan,
    "concurrency": 10,
    "requests-per-second": 8, # 0 means no limit
    "stop": stop, # 0 means continue forever
  },
  "query_parameters": {
    "no-networking": "true",
#    "commit-queue": "sync",
  }
}
