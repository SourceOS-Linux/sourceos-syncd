# Controller Event Contract

This document defines the first SourceOS controller-sovereignty event vocabulary. The goal is to make autonomous system behavior attributable, budgeted, and explainable.

A controller event is a durable record that says who acted, what authority was used, what resource class was touched, and what policy state resulted.

## Event envelope

```yaml
event_id: <stable-event-id>
event_type: ControllerRegistered
timestamp: <rfc3339>
host_ref: <redacted-host-ref>
controller_id: com.sourceos.example
controller_name: Example Controller
owner_trust_domain: first_party
source:
  service: <service-name>
  binary_ref: <redacted-binary-ref>
policy:
  profile: workstation
  decision: observed
  reason: <human-readable reason>
privacy:
  contains_private_payload: false
  redaction_level: summarized
```

## Required event types

### ControllerRegistered

Emitted when a controller becomes known to the system registry.

Required fields:

- `controller_id`
- `controller_name`
- `owner_trust_domain`
- `declared_capabilities`
- `declared_budgets`

### ControllerCapabilityDeclared

Emitted when a controller declares or changes an authority surface.

Capability classes:

- `network.physical_interface`
- `network.peer_interface`
- `network.tunnel`
- `network.proxy`
- `network.low_power_presence`
- `storage.file_read`
- `storage.file_write`
- `storage.database_mutation`
- `storage.indexing`
- `storage.filesystem_traversal`
- `cloud.sync`
- `cloud.push`
- `cloud.private_compute`
- `compute.cpu`
- `compute.gpu`
- `compute.accelerator`
- `power.idle_work`
- `power.sleep_work`

### ControllerBudgetObserved

Emitted when a controller consumes a measured budget interval without crossing a limit.

Required fields:

- `budget_class`
- `observed_amount`
- `budget_window`
- `policy_profile`

### ControllerBudgetExceeded

Emitted when a controller exceeds a declared budget.

Required fields:

- `budget_class`
- `observed_amount`
- `configured_limit`
- `budget_window`
- `platform_response`
- `recommended_user_action`

### ControllerTouchedResourceClass

Emitted when a controller touches a class of local state.

Resource classes:

- `user_documents`
- `media_library`
- `metadata_index`
- `filesystem_metadata`
- `application_cache`
- `cloud_sync_database`
- `network_configuration`
- `wireless_radio_state`
- `security_policy_state`

### ControllerOpenedNetworkSurface

Emitted when a controller opens or observes a network surface.

Surface classes:

- `physical_interface`
- `peer_wireless_interface`
- `tunnel_interface`
- `proxy_service`
- `name_resolution`
- `push_channel`
- `local_discovery`
- `service_proxy`

### ControllerEnteredIdleWork

Emitted when a controller begins work while the user is not actively foregrounding that controller.

Required fields:

- `controller_id`
- `idle_state`
- `declared_reason`
- `expected_duration`
- `budget_ref`

### ControllerExitedIdleWork

Emitted when an idle work interval completes.

Required fields:

- `controller_id`
- `duration`
- `resource_summary`
- `completion_state`

### ControllerPolicyChanged

Emitted when the effective policy profile changes for a controller.

Required fields:

- `previous_profile`
- `new_profile`
- `changed_by`
- `reason`

## Interpretation rule

Raw telemetry is not the product. The product is a stable diagnosis beside the raw signal. Every event should support an operator narrative:

> Controller X used capability Y under policy Z, consumed resource R, and left residual risk Q.

## Privacy rule

Controller events should be useful without exposing private payloads. Store file classes, service classes, redacted references, and aggregate resource amounts by default. Raw local artifacts stay local unless explicitly exported through a redaction workflow.
