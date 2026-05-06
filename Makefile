.PHONY: validate validate-json validate-control-plane

validate: validate-json validate-control-plane

validate-json:
	python3 - <<'PY'
	import json
	import pathlib
	import sys

	failed = False
	for root in (pathlib.Path('schemas'), pathlib.Path('examples')):
	    if not root.exists():
	        continue
	    for path in sorted(root.rglob('*.json')):
	        try:
	            json.loads(path.read_text())
	        except Exception as exc:
	            print(f'{path}: invalid JSON: {exc}', file=sys.stderr)
	            failed = True
	if failed:
	    raise SystemExit(1)
	print('JSON syntax validated.')
	PY

validate-control-plane:
	python3 tools/validate_control_plane_examples.py
