"""Package the working dir into an Agenomic bundle, push to cloud.

Reads:
  AGENOMIC_ENDPOINT, AGENOMIC_API_KEY, AGENOMIC_ORG_ID
  AGENOMIC_SIGNING_KEY_B64 (base64-encoded ed25519 private key)
  GITHUB_REF_NAME           (the tag, e.g. v0.1.0)

Writes:
  dist/bundle.tar.gz
  prints the release_id to stdout, also sets `release_id` GHA output
  if GITHUB_OUTPUT is set.
"""

from __future__ import annotations

import asyncio
import base64
import os
import sys
import tarfile
from pathlib import Path

from agenomic.client.client import AgenomicClient

AGENT_ID = "agent://traidano/codedrift"
BUNDLE_INCLUDE = ["src", "benchmarks", "agenomic.yaml", "pyproject.toml", "README.md"]


def make_archive(out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w:gz") as tar:
        for item in BUNDLE_INCLUDE:
            p = Path(item)
            if p.exists():
                tar.add(p, arcname=item)
    return out


async def push(archive: Path) -> dict[str, object]:
    endpoint = os.environ["AGENOMIC_ENDPOINT"]
    api_key = os.environ["AGENOMIC_API_KEY"]
    client = AgenomicClient(endpoint, api_key)
    try:
        upload_result = await client.upload_bundle(AGENT_ID, archive)
        bundle_id = upload_result["bundle"]["id"]
        version = os.environ.get("GITHUB_REF_NAME", "v0.0.0-local").lstrip("v")
        release = await client.create_release(
            {
                "agent_id": AGENT_ID,
                "bundle_id": bundle_id,
                "version": version,
                "notes": f"automated release from {os.environ.get('GITHUB_SHA', 'local')}",
            }
        )
        return release
    finally:
        await client.aclose()


def main() -> int:
    archive = make_archive(Path("dist/bundle.tar.gz"))
    print(f"packaged bundle: {archive} ({archive.stat().st_size} bytes)")

    key_b64 = os.environ.get("AGENOMIC_SIGNING_KEY_B64")
    if key_b64:
        Path("keys").mkdir(exist_ok=True)
        Path("keys/codedrift.priv").write_bytes(base64.b64decode(key_b64))

    release = asyncio.run(push(archive))
    release_id = release.get("release", {}).get("id")
    print(f"release_id={release_id}")

    out_path = os.environ.get("GITHUB_OUTPUT")
    if out_path and release_id:
        with open(out_path, "a", encoding="utf-8") as fp:
            fp.write(f"release_id={release_id}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
