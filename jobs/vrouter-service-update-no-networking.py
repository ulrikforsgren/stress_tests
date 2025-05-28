from stress_testing.parameters import SequenceRequest, RandomValue

start = 0
stop = 0
no_services = 1000
delay = 0
no_vlan = 1


intent = {
  "op": "update",
  "resource": "/vrouter:vrouter/service=K<<id>>",
  "data": {
    "service":{
      "delay": "<<delay>>",
      "template": "vlans",
      "device": "r<<id>>",
      "num-vlan": "<<numvlan>>",
      "str-value": "<<data>>"
    }
  },
  "query_parameters": {
    "no-networking": "true"
  }
}

parameters = {
    "id": SequenceRequest(start, wrap=no_services),
    "data": RandomValue(0, 4000000000),
    "delay": delay,
    "numvlan": no_vlan,
    "stop": stop
}
 