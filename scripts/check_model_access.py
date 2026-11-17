"""Check pinned publisher/mirror metadata without downloading model weights.

Only the manifest's public HTTPS endpoints are queried. No credentials are used.
The optional local-file check verifies actual bytes, rather than trusting metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def read_json(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": "SciViz-feasibility/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = response.read(2 * 1024 * 1024 + 1)
    if len(payload) > 2 * 1024 * 1024:
        raise ValueError("Metadata response exceeds the size limit")
    return json.loads(payload)


def publisher_file(document: dict, model: dict) -> dict:
    if document.get("id") != 140737:
        raise ValueError("Unexpected publisher model")
    versions = [v for v in document.get("modelVersions", []) if v.get("id") == model["version_id"]]
    files = [f for v in versions for f in v.get("files", []) if f.get("name") == model["filename"]]
    if len(files) != 1:
        raise ValueError("Pinned model version/file was not uniquely identified")
    file = files[0]
    if file.get("hashes", {}).get("SHA256", "").lower() != model["sha256"]:
        raise ValueError("Publisher checksum differs from pinned manifest")
    if round(file["sizeKB"] * 1024) != model["size_bytes"]:
        raise ValueError("Publisher size differs from pinned manifest")
    return file


def mirror_file(document: list, model: dict) -> dict:
    matches = [f for f in document if f.get("path") == model["mirror"]["filename"]]
    if len(matches) != 1:
        raise ValueError("Pinned mirror file was not uniquely identified")
    file = matches[0]
    if file.get("lfs", {}).get("oid", "").lower() != model["sha256"]:
        raise ValueError("Mirror checksum differs from publisher checksum")
    if file.get("size") != model["size_bytes"]:
        raise ValueError("Mirror size differs from publisher size")
    return file


def verify_local(path: Path, model: dict) -> dict:
    if path.stat().st_size != model["size_bytes"]:
        raise ValueError("Local checkpoint has the wrong size")
    with path.open("rb") as checkpoint:
        digest = hashlib.file_digest(checkpoint, "sha256").hexdigest()
    if digest != model["sha256"]:
        raise ValueError("Local checkpoint failed publisher checksum verification")
    return {"size_bytes": model["size_bytes"], "sha256": digest, "verified": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-file", type=Path, help="Also hash an already downloaded checkpoint")
    args = parser.parse_args()
    model = json.loads((ROOT / "space" / "models-manifest.json").read_text())["models"][0]
    report = {"schema_version": 1, "model": model["id"], "weights_downloaded": False}
    try:
        publisher_file(read_json(model["metadata_url"]), model)
        mirror = model["mirror"]
        url = f"https://huggingface.co/api/models/{mirror['repo']}/tree/{mirror['revision']}"
        mirror_file(read_json(url), model)
        report["publisher_and_mirror_metadata_match"] = True
        report["local_bytes"] = verify_local(args.local_file, model) if args.local_file else "not checked"
        report["status"] = "metadata_verified"
    except (OSError, ValueError, KeyError, TypeError) as error:
        report.update(status="failed", error_type=type(error).__name__)
        print(json.dumps(report, indent=2))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
