"""Bounded subprocess transport shared by the model and application adapters."""

import os
import selectors
import signal
import subprocess
import tempfile
import time

from . import OperationError


def run(command, *, timeout, cwd=None, input_bytes=b"", max_output=16 * 1024 * 1024, env=None):
    # A file avoids a stdin/stdout pipe deadlock for adapters that write early.
    with tempfile.TemporaryFile() as incoming:
        incoming.write(input_bytes)
        incoming.seek(0)
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=incoming,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        output = {"stdout": bytearray(), "stderr": bytearray()}
        size = 0
        deadline = time.monotonic() + timeout
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ, "stdout")
                selector.register(proc.stderr, selectors.EVENT_READ, "stderr")
                while selector.get_map():
                    left = deadline - time.monotonic()
                    if left <= 0:
                        raise OperationError("process timeout")
                    for key, _ in selector.select(left):
                        data = os.read(key.fileobj.fileno(), 65536)
                        if not data:
                            selector.unregister(key.fileobj)
                            continue
                        size += len(data)
                        if size > max_output:
                            raise OperationError("process output budget exhausted")
                        output[key.data].extend(data)
            try:
                code = proc.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                raise OperationError("process timeout") from None
            return code, bytes(output["stdout"]), bytes(output["stderr"])
        except BaseException:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            raise
        finally:
            proc.stdout.close()
            proc.stderr.close()
