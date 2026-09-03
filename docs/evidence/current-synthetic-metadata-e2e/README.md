# Current synthetic metadata end-to-end verification

This checked-in directory is a **frozen example snapshot** of the synthetic metadata evidence format. It is intentionally not rewritten after every source-code commit because the generated package contains timestamps, a package ID, and the generating Git HEAD.

For the current implementation, run:

```bash
python scripts/generate_public_evidence.py --output-dir /tmp/public-metadata-evidence
```

GitHub Actions runs the same generator for each verified commit and uploads the resulting `current-synthetic-metadata-e2e-<commit-sha>` artifact. That per-commit artifact is the authoritative current execution record; this checked-in snapshot is retained for direct browsing of the package shape.

The snapshot is synthetic verification, not a real-model result, real-video result, or historical benchmark. The synthetic PPM input and synthetic object facts are created by the harness. Metadata projection, asynchronous commit, indexes, source fingerprinting, archive linking, package verification, and replay use the extracted implementation paths listed in `run-config.json`.

Snapshot package: `packages/202609031353_10000_current_synthetic_verification`

The snapshot's `environment.json` and implementation hashes describe the checkout that generated this frozen snapshot. They must not be read as provenance for later commits; use the commit-scoped Actions artifact for that.
