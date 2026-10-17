"""Consumer adapter lifecycle and bounded HTTP control-plane transport.

The control plane belongs to an isolated test deployment, never the public
application API. It owns reset, fault injection, consistent snapshots and an
ordered effect journal. No expected model results are supplied to it.
"""

import copy
import json
import math
import re
import sys
import time
from urllib import error, parse, request

from . import MAX_BYTES, OperationError, _state
from .scenarios import _payload
from .system import canonical, digest

PROTOCOL = "capcov-scenario-adapter-v1"


def execute(payload, backend):
    """Run a history through a consumer-owned backend, releasing its lease.

    backend.describe() returns immutable build/config identity, command names
    and supported forced outcomes. acquire() allocates an exclusive disposable
    namespace. reset/snapshot/execute/release all receive that opaque lease.
    Partial acquire failures must be cleaned up by the backend itself.
    """
    if (
        not isinstance(payload, dict)
        or set(payload) != {"protocol", "initial", "steps"}
        or payload["protocol"] != PROTOCOL
    ):
        raise OperationError("invalid adapter input protocol")
    clean = _payload({"initial": payload["initial"], "steps": payload["steps"]}, 1024)
    # Do not permit oracle results even though scenario input accepts them.
    if clean != payload:
        raise OperationError("adapter input contains non-executable data")
    manifest = copy.deepcopy(backend.describe())
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"identity", "commands", "outcomes", "controls"}
        or not isinstance(manifest["identity"], str)
        or not manifest["identity"]
    ):
        raise OperationError("invalid backend manifest")
    for key in ("commands", "outcomes", "controls"):
        values = manifest[key]
        if (
            not isinstance(values, list)
            or not all(isinstance(v, str) and v for v in values)
            or len(set(values)) != len(values)
        ):
            raise OperationError("manifest entries must be distinct names")
    if not set(manifest["outcomes"]) <= {"committed", "aborted", "rejected"}:
        raise OperationError("invalid supported outcome")
    resolved = []
    for step in clean["steps"]:
        call = step["call"]
        outcome = call["outcome"]
        if outcome == "unknown":
            outcome = "committed" if step["choice"] == "1" else "aborted"
        if (
            call["command"] not in manifest["commands"]
            or outcome not in manifest["outcomes"]
        ):
            raise OperationError("unsupported command or outcome control")
        resolved.append(outcome)
    # Hash declarations to bind replay to the same deployment configuration.
    fingerprint = digest(manifest)
    lease = backend.acquire()
    try:
        backend.reset(lease, copy.deepcopy(clean["initial"]))
        initial = backend.snapshot(lease)
        _state(initial)
        if sorted(initial, key=canonical) != sorted(clean["initial"], key=canonical):
            raise OperationError("reset did not establish requested initial state")
        observations = []
        for index, (step, outcome) in enumerate(zip(clean["steps"], resolved)):
            response = backend.execute(
                lease, index, copy.deepcopy(step["call"]), outcome
            )
            if (
                not isinstance(response, dict)
                or set(response) != {"outcome", "observation"}
                or response["outcome"] != outcome
            ):
                raise OperationError("backend did not attest selected outcome")
            observation = response["observation"]
            if not isinstance(observation, dict) or set(observation) != {
                "state",
                "effects",
            }:
                raise OperationError("invalid backend observation")
            _state(observation["state"])
            if not isinstance(observation["effects"], list):
                raise OperationError("effects must be an ordered journal")
            observations.append(copy.deepcopy(observation))
        if backend.describe() != manifest:
            raise OperationError("backend deployment identity changed")
        return {
            "protocol": PROTOCOL,
            "choices": [s["choice"] for s in clean["steps"]],
            "controls": ["backend-manifest:" + fingerprint, *manifest["controls"]],
            "observations": observations,
        }
    finally:
        # Release failure is an operational failure, never successful evidence.
        backend.release(lease)


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise OperationError("adapter control plane redirects are forbidden")


class HTTPBackend:
    """JSON control plane with deadline checks, response limits and no retries.

    bearer is supplied by the caller (normally from an environment variable).
    It is never included in evidence. Session tokens are restricted opaque IDs.
    A server-side lease expiry is mandatory for process death/network partitions.
    """

    def __init__(self, base_url, *, bearer=None, timeout=60, cleanup_timeout=5):
        url = parse.urlsplit(base_url)
        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise OperationError(
                "control URL must be an HTTP(S) origin/path without credentials"
            )
        if (
            bearer
            and url.scheme != "https"
            and url.hostname not in ("localhost", "127.0.0.1", "::1")
        ):
            raise OperationError(
                "bearer authentication requires HTTPS outside loopback"
            )
        if any(
            type(t) not in (int, float) or not math.isfinite(t) or t <= 0
            for t in (timeout, cleanup_timeout)
        ):
            raise OperationError("adapter deadlines must be finite and positive")
        self.base = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        if bearer:
            self.headers["Authorization"] = "Bearer " + bearer
        self.deadline = time.monotonic() + timeout
        self.cleanup_timeout = cleanup_timeout
        self.opener = request.build_opener(request.ProxyHandler({}), _NoRedirect())

    def _send(self, path, data, *, cleanup=False):
        remaining = (
            self.cleanup_timeout if cleanup else self.deadline - time.monotonic()
        )
        if remaining <= 0:
            raise OperationError("adapter deadline exceeded")
        raw = canonical(data).encode()
        if len(raw) > 4 * MAX_BYTES:
            raise OperationError("adapter request exceeds limit")
        req = request.Request(
            self.base + path, data=raw, headers=self.headers, method="POST"
        )
        try:
            with self.opener.open(req, timeout=remaining) as response:
                if response.status != 200:
                    raise OperationError("control plane returned unexpected status")
                # read1 bounds each blocking read; check the total deadline too.
                chunks, size = [], 0
                end = time.monotonic() + remaining if cleanup else self.deadline
                while True:
                    if time.monotonic() >= end:
                        raise OperationError("adapter response deadline exceeded")
                    chunk = response.read1(min(65536, 4 * MAX_BYTES + 1 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > 4 * MAX_BYTES:
                        raise OperationError("adapter response exceeds limit")
                value = json.loads(b"".join(chunks))
                return value
        except (error.URLError, OSError, ValueError) as exc:
            # Do not echo response bodies, URLs or authentication material.
            raise OperationError("HTTP adapter transport failed") from exc

    @staticmethod
    def _path(lease, action):
        if not isinstance(lease, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,128}", lease
        ):
            raise OperationError("invalid session lease")
        return "/sessions/" + lease + "/" + action

    def describe(self):
        return self._send("/describe", {})

    def acquire(self):
        result = self._send("/sessions", {})
        if not isinstance(result, dict) or set(result) != {"lease"}:
            raise OperationError("invalid session allocation")
        self._path(result["lease"], "reset")
        return result["lease"]

    def reset(self, lease, initial):
        if self._send(self._path(lease, "reset"), {"initial": initial}) != {"ok": True}:
            raise OperationError("reset failed")

    def snapshot(self, lease):
        return self._send(self._path(lease, "snapshot"), {})

    def execute(self, lease, index, call, outcome):
        return self._send(
            self._path(lease, "execute"),
            {"index": index, "call": call, "outcome": outcome},
        )

    def release(self, lease):
        if self._send(self._path(lease, "release"), {}, cleanup=True) != {"ok": True}:
            raise OperationError("session release failed")


def main(argv=None):
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description="Run an isolated HTTP scenario control plane"
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--token-env")
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args(argv)
    try:
        token = os.environ[args.token_env] if args.token_env else None
        payload = json.loads(sys.stdin.buffer.read(4 * MAX_BYTES + 1))
        print(
            json.dumps(
                execute(
                    payload, HTTPBackend(args.url, bearer=token, timeout=args.timeout)
                )
            )
        )
        return 0
    except (ValueError, KeyError, OSError):
        print('{"operational_failure":"adapter execution failed"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
