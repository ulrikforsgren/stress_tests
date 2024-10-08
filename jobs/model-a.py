from stress_testing.stress_testing import SequenceRequest, RandomValue

DATA = \
{
  "op": "update",
  "url": "/model-a:model-a/model-a:list=K<<id>>",
  "data": {
    "list":{
        "str-value": "Changed string data <<data>>",
        "int-value": "<<data>>"
    }
  },
  "parameters": {
    "id": SequenceRequest(0, wrap=1000),
    "data": RandomValue(0, 4000000000)
  }
}