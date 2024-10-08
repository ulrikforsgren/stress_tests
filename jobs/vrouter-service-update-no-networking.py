from stress_testing.stress_testing import SequenceRequest, RandomValue

DATA = \
{
  "op": "update",
  "url": "/vrouter:vrouter/service=K<<id>>",
  "data": {
    "service":{
      "delay": "<<delay>>",
      "template": "vlans",
      "device": "r<<id>>",
      "num-vlan": "<<numvlan>>",
      "str-value": "<<data>>"
    }
  },
  "parameters": {
    "id": SequenceRequest(0, wrap=1000),
    "data": RandomValue(0, 4000000000),
    "delay": 0,
    "numvlan": 1
  },
  "params": {"no-networking": "true"}
}