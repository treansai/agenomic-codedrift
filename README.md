# agenomic-codedrift

End-to-end test agent for the [Agenomic](https://agenomic.dev) platform.

A LangGraph agent that prompts Claude with a fixed benchmark of 5 Python
snippets, scores the refactored output with `ruff` / `radon` / `bandit`,
and reports per-metric drift versus a 30-day rolling baseline. Each run
emits a signed `TraceEnvelope` to Agenomic Cloud.

This project exists primarily to exercise the full Agenomic platform —
bundle versioning, signing, registry push, trace upload, attestation
linkage — on a continuous schedule (GitHub Actions cron, every 6 hours).

## Quickstart

```bash
git clone https://github.com/treansai/agenomic-codedrift
cd agenomic-codedrift
make install
make test
```

To run the agent against a real Anthropic + Agenomic backend:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export AGENOMIC_ENDPOINT=https://api.agenomic.example
export AGENOMIC_API_KEY=agm_...   # legacy alk_… keys also work
make e2e
```

## Layout

| Path                                  | Purpose                                                   |
|---------------------------------------|-----------------------------------------------------------|
| `benchmarks/*.py`                     | 5 frozen un-idiomatic snippets                            |
| `src/agenomic_codedrift/graph.py`     | LangGraph wiring (5 sequential nodes)                     |
| `src/agenomic_codedrift/nodes.py`     | load → prompt → score → compare → emit                    |
| `src/agenomic_codedrift/metrics.py`   | ruff / radon / bandit subprocess wrappers                 |
| `src/agenomic_codedrift/baseline.py`  | JSONL persistence + per-snippet drift math                |
| `src/agenomic_codedrift/claude.py`    | Anthropic SDK wrapper with exponential backoff            |
| `agenomic.yaml`                       | Bundle manifest (version, signing, schema)                |
| `.github/workflows/`                  | CI, release (bundle push on tag), drift (cron 6h)         |

## Bundle release

Tag the repo to trigger the bundle push:

```bash
git tag v0.1.0
git push origin v0.1.0
```

`release.yml` packages `src/`, `benchmarks/`, `agenomic.yaml`, and
`pyproject.toml` into a tarball, signs it with the ed25519 key stored
in the `AGENOMIC_SIGNING_KEY_B64` GitHub secret, and pushes via
`AgenomicClient.upload_bundle` + `create_release`. The resulting
release id is exported as `AGENOMIC_RELEASE_ID` for the drift cron.

## License

Copyright (C) 2026 Agenomic Contributors. GNU Affero General Public License
v3.0 (`AGPL-3.0-only`). See [LICENSE](LICENSE).

This repository is part of the Agenomic Community edition. Agenomic Cloud and
Enterprise components live in separate, private repositories and are not
covered by this license.
