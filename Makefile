.PHONY: validate validate-json validate-schemas validate-control-plane validate-eventctl validate-event-store validate-events validate-identity validate-process-provenance validate-policy-normalizer validate-service-graph validate-semantic-enterprise-state-integrity install-dev

validate: validate-json validate-schemas validate-control-plane validate-eventctl validate-event-store validate-events validate-identity validate-process-provenance validate-policy-normalizer validate-service-graph validate-semantic-enterprise-state-integrity

install-dev:
	python3 -m pip install -r requirements-dev.txt

validate-json:
	python3 tools/validate_json_syntax.py

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
	python3 tools/smoke_identity_audit.py

validate-process-provenance:
	python3 tools/sourceos_process_provenance.py validate examples/process-provenance/package-shell.provenance.json
	python3 tools/sourceos_process_provenance.py emit-events examples/process-provenance/package-shell.provenance.json >/dev/null
	! python3 tools/sourceos_process_provenance.py validate examples/process-provenance/invalid/bad-path-class.provenance.json

validate-policy-normalizer:
	python3 tools/sourceos_policy_normalizer.py validate-registry
	python3 tools/sourceos_policy_normalizer.py validate-observation examples/policy-observations/expected-metadata-boundary.json
	python3 tools/sourceos_policy_normalizer.py validate-observation examples/policy-observations/expected-network-disabled.json
	python3 tools/sourceos_policy_normalizer.py validate-observation examples/policy-observations/degraded-trust-local-only.json
	python3 tools/sourceos_policy_normalizer.py validate-observation examples/policy-observations/attack-like-privilege-boundary-probe.json
	python3 tools/sourceos_policy_normalizer.py normalize examples/policy-observations/expected-metadata-boundary.json >/dev/null
	python3 tools/sourceos_policy_normalizer.py normalize examples/policy-observations/expected-network-disabled.json >/dev/null
	python3 tools/sourceos_policy_normalizer.py normalize examples/policy-observations/degraded-trust-local-only.json >/dev/null
	python3 tools/sourceos_policy_normalizer.py normalize examples/policy-observations/attack-like-privilege-boundary-probe.json >/dev/null
	! python3 tools/sourceos_policy_normalizer.py validate-observation examples/policy-observations/invalid/expected-boundary-as-attack-like.json

validate-service-graph:
	python3 tools/sourceos_service_graph.py validate examples/services/*.json
	python3 tools/sourceos_service_graph.py graph examples/services/*.json --json >/dev/null

validate-semantic-enterprise-state-integrity:
	python3 tools/validate_semantic_enterprise_state_integrity.py
