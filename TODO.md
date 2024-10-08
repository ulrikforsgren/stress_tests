# Stress Testing Framework

## TODO

- How to push services and wait for them to complete.
- Log results to file.
- Color parameters output for readability
- Improve coloring of output.

- Copy cisco-ios-cli-3.o0 NED from distribution.
- Choose batch or sliding window
- Catch exception(s) and KeyBoardInterrupt
- Better formatting of title in HTML.
- Pause job? (must be implemented per job type e.g sliding_window)
- Fix how __repr__, __str__ and current are used in class Parameter etc.
- Fix how values are update between requests e.g random values.
- Print last value for all Parameters
- Update parameters comments for all tests
- Write ongoing op before stress requests (progress bar?)
- Color stress tests output.
- Support RequestBatch even for sliding_window_executor
- Unify executors
- Update ContextValue to read from NSO
