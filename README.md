# Simple NSO Performance, Scalability and Stress Tests #

## Overview

The idea is to provide a simple framework for running tests and get metrics of
the behavior of NSO depending on a number of factors:

* Standalone or HA setup
* LSA
* Use of commit-queues
* Service create code execution time.
* Network latency between NSO nodes for CDB replication.
* Synchronous/Asynchronous CDB replication.
* Network latency towards devices.
* Size of generated device configuration.
* Use of different northbound APIs: RESTCONF/NETCONF
* Use of different service types: template, Python, Java, ...
* ...

## Strategy

The framework is intended to be simplistic, easy to setup and parameterized to
allow for setting up defferent envirionments and run tests to compare setups.

The first tests will just test CRUD of a simple model without involvment of any
service functionality. Just to get the really basic performance and behavior of
the raw northbound API and see how it scales.

Additional tests will then be created, adding more features in small increments.
This will allow for better interpretation of the produced metrics as any changes
are more easily related to what has changed.

So far these increments have come to mind:
1. Complement create/delete test with an intermediate update.
2. Run tests using NETCONF
3. Simple template based empty service, i.e. does not create any device config.
4. Simple Python based empty service, i.e. does not create any device config.

## Dimensions and Permutations ##

There are several dimensions on how to look at how at and how to combine
features of NSO. On top of that a number of ways to use the system can be
applied.

System wide features:
* HA is an on/off feature applied on the total system.
    * Latency can be interesting to adjust between the NSO nodes.
* LSA is a design pattern applied on the total system.
* Commit Queues is a behavioral feature and is normally applied to the whole
  system.

Service features:
* Type: template/Python/Python+template/Java/Java+template/Nano
* RFM in combination with Python or Java
* Nano services callbacks
* Plan data

Other features:
* Kickers
* Subscribers: Python/Java?

