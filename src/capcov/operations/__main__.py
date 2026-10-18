"""python -m capcov.operations --spec MODEL.op --request INPUT.json [--out FILE]."""
import argparse
import json
from pathlib import Path
import sys
from . import execute, OperationError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--timeout', type=float, default=30)
    args = parser.parse_args()
    try:
        result = execute(args.spec.read_text(encoding='utf-8'),
                         json.loads(args.request.read_text(encoding='utf-8')), timeout=args.timeout)
    except (OperationError, ValueError, OSError) as exc:
        print(json.dumps({'operational_failure':str(exc)}), file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.out:
        args.out.write_text(text, encoding='utf-8')
    else:
        print(text, end='')
    return 1 if (result['observed_matches'] is False or result['trace_valid'] is False) else 0


if __name__ == '__main__':
    raise SystemExit(main())
