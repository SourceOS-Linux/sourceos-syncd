# Process Provenance Examples

These examples exercise `schemas/sourceos.process-provenance.v0.1.schema.json` and the canonical process lifecycle flow.

## Valid fixtures

- `package-shell.provenance.json`: package-managed shell launch with clean exit, local-first trust posture, package-origin classification, and privacy-preserving path handling.

## Invalid fixtures

- `invalid/bad-path-class.provenance.json`: uses an unsupported executable `path_class` and must fail validation.

## Validation contract

```bash
python3 tools/sourceos_process_provenance.py validate examples/process-provenance/package-shell.provenance.json
python3 tools/sourceos_process_provenance.py emit-events examples/process-provenance/package-shell.provenance.json
! python3 tools/sourceos_process_provenance.py validate examples/process-provenance/invalid/bad-path-class.provenance.json
```

The Makefile exposes this as:

```bash
make validate-process-provenance
```

The full validation contract includes it through:

```bash
make validate
```

## Design intent

Process provenance is separate from raw process logging. The tuple captures the stable facts needed to generate canonical SourceOS lifecycle events:

- process identity class;
- executable identity class;
- package/source origin;
- signature/trust posture;
- parent/root trace assignment;
- exit status when observed;
- privacy-tiered disclosure boundaries.

The generated events should attach process launch and process exit to the same `trace_id` and `root_event_id`, rather than generating unrelated operator noise.
