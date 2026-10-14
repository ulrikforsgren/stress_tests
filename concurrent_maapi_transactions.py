#!/usr/bin/env python3
"""Run a configurable number of independent NSO MAAPI write transactions.

The callback must be importable as ``module:function`` and accept
``(worker_name, transaction, maagic_root, intent)``. For example:

    python concurrent_maapi_transactions.py -c 4 -n 100 -f workload:add_item

Run from an NSO Python environment (for example, after sourcing ``ncsrc``).
"""

import argparse
from importlib import import_module
import multiprocessing
import time
from typing import NamedTuple


class Intent(NamedTuple):
    """The work item assigned to a worker process."""

    name: str
    i: int

_callback_spec = None
_callback = None
_ncs = None
_user = None
_context = None


def positive_int(value):
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def load_callback(spec):
    print("Loading callback", flush=True)
    """Load a module-level callback named ``module:function``."""
    module_name, separator, function_name = spec.partition(":")
    if not separator or not module_name or not function_name:
        raise ValueError("callback must use the form module:function")
    callback = getattr(import_module(module_name), function_name)
    if not callable(callback):
        raise ValueError(f"{spec!r} does not refer to a callable")
    print("Callback loaded", flush=True)
    return callback


def initialize_worker(callback_spec, user, context):
    """Save configuration in each child; imports occur on its first task."""
    global _callback_spec, _user, _context

    _callback_spec = callback_spec
    _user = user
    _context = context


def execute_intent(intent):
    """Prepare the MAAPI transaction and root, run the callback, and commit."""
    print("Executing intent")
    global _callback, _ncs
    if _ncs is None:
        print("importing ncs")
        # Import NSO's API and callback in the child process. This also keeps
        # module loading safe when multiprocessing uses the spawn start method.
        import ncs

        _ncs = ncs
        _callback = load_callback(_callback_spec)

    print("Transaction creating", _user, _context)
    with _ncs.maapi.single_write_trans(_user, _context) as transaction:
        print("Transaction created", flush=True)
        root = _ncs.maagic.get_root(transaction)
        worker_name = multiprocessing.current_process().name
        _callback(worker_name, transaction, root, intent)
        print("Transacioun applying", flush=True)
        transaction.apply()
        print("Transaction done", flush=True)
    return intent.name


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-c", "--concurrency", type=positive_int, required=True,
        help="number of worker processes (concurrent transactions)",
    )
    parser.add_argument(
        "-n", "--transactions", type=positive_int, required=True,
        help="total number of transactions to execute",
    )
    parser.add_argument(
        "-f", "--function", required=True, metavar="MODULE:CALLABLE",
        help="importable callback accepting worker name, transaction, root, and intent",
    )
    parser.add_argument(
        "--user", default="admin", help="NSO user (default: admin)",
    )
    parser.add_argument(
        "--context", default="system", help="NSO context (default: system)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        # Build all work items in the parent before submitting them to workers.
        intents = [Intent(name=f"intent-{index:06d}", i=index)
                   for index in range(0, args.transactions)]
        context = multiprocessing.get_context("spawn")
        with context.Pool(
            processes=args.concurrency,
            initializer=initialize_worker,
            initargs=(args.function, args.user, args.context),
        ) as pool:
            completed = sum(1 for _ in pool.imap_unordered(
                execute_intent, intents, chunksize=1))
            time.sleep(60)
    except KeyboardInterrupt:
        raise SystemExit("Interrupted; active worker processes were stopped.")

    print(f"Completed {completed} transactions using {args.concurrency} workers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
