# Stress Testing Framework

## TODO

### Working on



### High Priority

- Better back propagation mechanism for results.
  - Handle multiprocessing, threading and asyncio
  - ayncio.Queue compatible wrapper for multiprocessing.Queue and queue.Queue
    - Works with both asyncio and plain Python.


### Medium Priority

- Handle ctrl-c
    - Catch exception(s) and KeyBoardInterrupt
    - Fix close_flag

- Log results to file (csv).
- Write annotations to Grafana


### Low Priority

- Copy cisco-ios-cli-3.o0 NED from distribution.
- Support save/restore state.
    - Pause job? (must be implemented per job type e.g sliding_window)
- Objectify restconf_api etc.
- Separate intent parameters and metrics?

- Parameters:
    - Update ContextValue to read from NSO.
        - When task is started?
    - Rename Calc.
    - Make overridable.
    - Simplify usage.
    - Generic design pattern (resuability etc.)

- Improve output:
    - Show last/current value of Parameters for "show" command.
    - Write ongoing op before stress requests (progress bar?)
    - Color stress tests output.
    - Improve coloring of output.
    - Color parameters output for readability.
    - Better formatting of title in HTML.

- Export metrics from benchmarking-nso.
- Auto scale concurrency to maintain requests-per-second.
- Make grpc port (50052) configurable.
- Choose batch or sliding window executor.


## Completed

- Update parameters comments for all tests. ✅
- Handle change in concurrency. 
- Unify execution function headers. ✅
- Improve dry-run echo. ✅
  - Show URL, URL + intent, intent. ✅
- Unified terminology: intent/task_args, parameters, ... ✅
- Unify executors. ✅
  - Merge sliding_window_executors. ✅
- Create run_crud_test.py runner script
    - Convert tests into job like Python files.
- Use common ParseArgs framework. ✅
    - tests ✅
    - benchmarking-nso ✅
    - ssts_scale_tests ✅
- Support RequestBatch even for sliding_window_executor. ✅
    - Preparing the requests must be done in a synchronous way. Currently not :(
- Fix how __repr__, __str__, val and current are used in class Parameter etc. ✅
  - Print last value for all Parameters. ✅
  - Fix __deepcopy__ to copy current state. TDB
- Fix how values are update between requests e.g random values. ✅
  - Refactor Parameters to support predictable sequences with multiple sequences 
    incl. pseudo random sequences. 
- Wrap random sequence after n requests. ✅
- Split stress_testing.py:
  - Executors ✅
  - ArgParsers ✅
  - Runners (CRUD, single test, ...) ✅
  - Parameters ✅
  - Tasks ✅



## Notes:

Executors:
- batch_executor (unused)
- sliding_window_executor
- single_request


Tasks:
- default_task

Runners:
- run_test
  - run_tests
    - run_test_in_subprocess
      - do_test
         - executor
  - run_single_test
- run_crud_tests (not used)
- benchmarking-nso
- ssts_scale_test

ArgParsers:
- benchmarking-nso
- stress_tests
- ssts_scale_test



# #############################################################
# __repr__, __str__
# update_str, update_batch, update_request
# Parameter, Sequence, Calc

* Value should be generated upon request.
    - Possible to know when it has been been used or not.
    - Can return last value
    - __str__ get current value as a string '<no value>' when no updated.
    - __repr__ get representation of object and parameters
    - self.current stores the current value


default_task (called before each request)
    parameters.update_request()
    format_parameters (first on resource, then data)
        Parameter.update_str()



# When should they be used and what should they return?

__repr__:
    Return:  <type>(current value, parameters)

__str__:
    Returns: string representation of current value
             '<no value>' if not set.

current:                   
    stores the current value

update_str:                 Called before each usage
    Usage:
        default_task
            format_parameters

update_request:             Called before preparing each request.
    Usage:
        default_task before format_parameters

update_batch:               Called before preparing every 'concurrency:th' request.
    Usage:
        batch_executer
        sliding_window_executor