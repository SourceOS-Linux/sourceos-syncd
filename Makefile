.PHONY: validate validate-json validate-schemas validate-control-plane validate-eventctl validate-event-store validate-events validate-identity install-dev

validate: validate-json validate-schemas validate-control-plane validate-eventctl validate-event-store validate-events validate-identity

install-dev:
	python3 -m pip install -r requirements-dev.txt

validate-json:
	python3 -c "import json, pathlib, sys; failed=False; roots=(pathlib.Path('schemas'), pathlib.Path('examples'));\nfor root in roots:\n    if not root.exists():\n        continue\n    for path in sorted(root.rglob('*.json')):\n        try:\n            json.loads(path.read_text())\n        except Exception as exc:\n            print(f'{path}: invalid JSON: {exc}', file=sys.stderr); failed=True\nif failed:\n    raise SystemExit(1)\nprint('JSON syntax validated.')"

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

validate-event-store:
	python3 tools/smoke_event_store.py

validate-events:
	python3 tools/validate_events.py

validate-identity:
	python3 tools/sourceos_identity_audit.py \
		--service examples/services/bearbrowser.service.json \
		--launch examples/launch/bearbrowser.launch-manifest.json
