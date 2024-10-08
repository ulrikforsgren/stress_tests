from stress_testing.stress_testing import SequenceRequest, RandomValue

DATA = \
{
  "op": "create",
  "url": "/vrouter:vrouter",
  "data": {
    "service":{
      "name": "K<<id>>",
      "delay": "<<delay>>",
      "template": "vlans",
      "device": "r<<id>>",
      "str-value": "<<data>>",
      "num-vlan": 1
    }
  },
  "parameters": {
    "id": SequenceRequest(0),
    "data": RandomValue(0, 4000000000),
    "delay": 0,
    "stop": 1000
  }
}