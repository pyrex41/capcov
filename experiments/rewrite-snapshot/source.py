"""One reset workflow against the real Capcov filesystem-backed CAS."""
import json
import sys
import tempfile
from capcov.cas import SnapshotStore, MissingBlobError, InvalidManifestError


def run(history):
    with tempfile.TemporaryDirectory() as root:
        store = SnapshotStore(root)
        blobs, snapshots, trace = {}, {}, []
        for op, *args in history:
            try:
                if op == 'blob':
                    name, text = args
                    result = blobs[name] = store.cas.put_bytes(text.encode())
                elif op == 'publish':
                    name, paths, parent, metadata = args
                    files = {p: blobs.get(b, '0'*64) for p, b in paths}
                    parent = snapshots.get(parent, '0'*64) if parent is not None else None
                    result = store.put(files, parent=parent, metadata=metadata)
                    snapshots[name] = result
                elif op == 'read':
                    result = store.read(snapshots[args[0]]).decode()
                else: raise ValueError(op)
                trace.append({'ok':result})
            except (KeyError, FileNotFoundError): trace.append({'error':'missing'})
            except MissingBlobError: trace.append({'error':'missing_blob'})
            except InvalidManifestError: trace.append({'error':'manifest'})
        return trace


if __name__=='__main__': print(json.dumps([run(h) for h in json.load(sys.stdin)]))
