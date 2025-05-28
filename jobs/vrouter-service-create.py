from stress_testing.parameters import SequenceRequest, RandomValue

start = 0
wrap = 1000
stop = 0
delay = 0
no_vlan = 1


intent = {
  "op": "create",
  "resource": "/vrouter:vrouter",
  "data": {
    "service":{
      "name": "S<<id>>",
      "delay": "<<delay>>",
      "template": "vlans",
      "device": "r<<id>>",
      "str-value": "<<data>>",
      "num-vlan": no_vlan
    }
  }
}

parameters = {
    "id": SequenceRequest(start),
    "data": RandomValue(start, 4000000000),
    "delay": delay,
    "stop": stop
}
