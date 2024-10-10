# Stress Testing Framework

## TODO

### Working on

### High Priority

- Fix how __repr__, __str__ and current are used in class Parameter etc.
  - Print last value for all Parameters.

- Fix how values are update between requests e.g random values.
  - Refactor Parameters to support predictable sequences with multiple sequences incl. pseudo 
    random sequences.
- Support RequestBatch even for sliding_window_executor
- Wrap random sequence after n requests.
- Better back propagation mechanism for results.
  - Handle multiprocessing, threading and asyncio
  - ayncio.Queue compatible wrapper for multiprocessing.Queue and queue.Queue
    - Works with both asyncio and plain Python.


### Medium Priority

- Handle ctrl-c
    - Catch exception(s) and KeyBoardInterrupt
    - Fix close_flag

- Split stress_testing.py:
  - Executors
  - ArgParsers
  - Runners (CRUD, single test, ...)
  - Tasks
  - Etc.

- Log results to file (csv).
- Write annotations to Grafana


### Low Priority

- How to push services and wait for them to complete.
- Copy cisco-ios-cli-3.o0 NED from distribution.
- Update ContextValue to read from NSO.
    - When task is started?
- Support save/restore state.
    - Pause job? (must be implemented per job type e.g sliding_window)
- Objectify restconf_api etc.
- Rename Calc.
  - Make overridable.
  - Simplify usage.
  - Generic design pattern (resuability etc.)
- Move away from **task_args?
- Separate intent parameters and metrics?
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
