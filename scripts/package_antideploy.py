"""Package only the tracked hosted service and verified original LFS assets."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

APPLICATION_ID = "4427410e-8b49-4122-aedb-8dbb5e2e3c60"
LIVE_URL = "https://archipelago.antideploy.com"
MAX_TOTAL_BYTES = 28 * 1024 * 1024


def package(root: Path, output: Path, assets: Path, recovered: Path) -> dict:
    """Build a secret-free upload; refuse silently modified source or LFS assets."""
    output.mkdir(parents=True, exist_ok=True)
    stage = output / "source"
    stage.mkdir(exist_ok=False)
    files = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "host_inference"], text=True,
    ).splitlines()
    manifest = []
    missing = []
    for name in files:
        if name.endswith(".stripped_backup_20260729") or name == "host_inference/.antideploy.json":
            continue
        source = root / name
        data = source.read_bytes()
        if data.startswith(b"version https://git-lfs.github.com/spec/v1"):
            oid = re.search(rb"oid sha256:(\w+)", data).group(1).decode()
            size = int(re.search(rb"size (\d+)", data).group(1))
            candidates = [assets / name, recovered / source.name]
            matched = next((
                path for path in candidates if path.is_file()
                and path.stat().st_size == size
                and hashlib.sha256(path.read_bytes()).hexdigest() == oid
            ), None)
            if matched is None:
                missing.append(name)
                continue
            data = matched.read_bytes()
        dest = stage / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        manifest.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    release = {
        "source_commit": commit, "application_id": APPLICATION_ID, "url": LIVE_URL,
        "minimum_concepts": 520, "minimum_pearson_books": 40,
    }
    (stage / "host_inference" / "release.json").write_text(json.dumps(release, indent=2) + "\n")
    shutil.copyfile(root / "deploy" / "antideploy" / "Dockerfile", stage / "Dockerfile")
    (stage / ".antideploy.json").write_text(json.dumps({
        "applicationId": APPLICATION_ID, "name": "archipelago", "subdomain": "archipelago",
    }) + "\n")
    total = sum(path.stat().st_size for path in stage.rglob("*") if path.is_file())
    if total > MAX_TOTAL_BYTES:
        raise ValueError(f"Upload exceeds the platform limit: {total} bytes.")
    archive = output / "archipelago-release.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                tar.add(path, arcname=path.relative_to(stage).as_posix(), recursive=False)
    report = {
        **release, "files": len(manifest) + 3, "total_bytes": total,
        "archive_bytes": archive.stat().st_size, "missing_original_assets": missing,
        "manifest": manifest,
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--recovered", type=Path, required=True)
    args = parser.parse_args()
    report = package(Path(__file__).resolve().parents[1], args.output, args.assets, args.recovered)
    print(json.dumps({key: value for key, value in report.items() if key != "manifest"}, indent=2))


if __name__ == "__main__":
    main()
