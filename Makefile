.PHONY: validate validate-json validate-schemas validate-control-plane validate-eventctl install-dev

validate: validate-json validate-schemas validate-control-plane validate-eventctl

install-dev:
	python3 -m pip install -r requirements-dev.txt

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

validate-schemas:
	python3 tools/validate_json_schemas.py

validate-control-plane:
	python3 tools/validate_control_plane_examples.py

validate-eventctl:
	python3 tools/sourceos_eventctl.py validate examples/events/apple-mdm-entitlement-denial.coalesced.json
	python3 tools/sourceos_eventctl.py explain examples/events/apple-darkwake-network-receipt.json >/dev/null
	python3 tools/sourceos_eventctl.py emit-policy-decision \
		--actor sourceos-policy-engine \
		--subject com.example.target \
		--policy-rule sourceos.example.deny \
		--operation ipc.lookup.example \
		--target-class example_ipc_service \
		--explanation-code POLICY_EXPECTED_TEST_BOUNDARY \
		--summary 'Example expected policy boundary was enforced.' \
		--why 'This smoke test proves generated policy-decision events validate against the canonical schema.' \
		--next-action 'No action required.' >/dev/null
