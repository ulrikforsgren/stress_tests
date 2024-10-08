# Stress Testing Framework

## TODO

### High Priority
- Fix how __repr__, __str__ and current are used in class Parameter etc.
- Fix how values are update between requests e.g random values.
  - Refactor Parameters to support predictable sequences with multiple sequences incl. pseudo 
    random sequences.
- Wrap random sequence after n requests.
- Better back propagation mechanism for results.
  - Handle multiprocessing, threading and asyncio
  - ayncio.Queue compatible wrapper for multiprocessing.Queue and queue.Queue
    - Works with both asyncio and plain Python.

### Medium Priority
- Catch exception(s) and KeyBoardInterrupt
- Unify executors
- Split stress_testing.py:
  - Executors
  - ArgParsers
  - Runners (CRUD, single test, ...)
  - Tasks
  - Etc.
- Support RequestBatch even for sliding_window_executor
- Choose batch or sliding window
- Log results to file (csv).
- Improve dry-run echo
  - Show URL, URL + intent, intent
- Write annotations to Grafana

### Low Priority

- How to push services and wait for them to complete.
- Copy cisco-ios-cli-3.o0 NED from distribution.
- Update ContextValue to read from NSO.
- Support save/restore state.
- Pause job? (must be implemented per job type e.g sliding_window)
- Objectify restconf_api etc.
- Rename Calc.
  - Make overridable.
  - Simplify usage.
  - Generic design pattern (resuability etc.)
- Move away from **task_args?
- Separate intent parameters and metrics?
- Show last/current value of Parameters for "show" command.
- Write ongoing op before stress requests (progress bar?)
- Color stress tests output.
- Color parameters output for readability.
- Improve coloring of output.
- Better formatting of title in HTML.
- Print last value for all Parameters.
- Export metrics from benchmarking-nso.
- Auto scale concurrency to maintain requests-per-second.
- Make grpc port (50052) configurable.



## Completed

- Update parameters comments for all tests. ✅
- Handle change in concurrency. ✅



## Notes:

Executors:
- stress_requests_batch (unused)
- stress_requests_window
- single_request
- sliding_window_executor (benchmarking-nso)
- throttling_executor (benchmarking-nso)

Tasks:
- default_task

Runners:
- run_test
  - run_tests
    - run_test_in_subprocess
      - do_test
         (stress_requests_window)
  - run_single_test
- run_crud_tests (not used)
- benchmarking-nso
- ssts_scale_test

ArgParsers:
- benchmarking-nso
- stress_tests
- ssts_scale_test
