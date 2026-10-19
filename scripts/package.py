"""Create Adaptive AI style addon-root, repository, and combined release ZIPs."""
from __future__ import annotations
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "ubox_bridge"
VERSION = (ADDON / "APP_VERSION").read_text(encoding="utf-8").strip()
RELEASE = ROOT / "release"
RELEASE.mkdir(exist_ok=True)

def make_zip(output: Path, files: list[tuple[Path, str]]):
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for src, archive_name in sorted(files, key=lambda p: p[1]):
            z.write(src, archive_name)
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:
            raise ValueError("corrupted ZIP: " + str(output))

def collect(directory: Path):
    return [p for p in directory.rglob("*") if p.is_file()
            and ".git" not in p.parts and "__pycache__" not in p.parts
            and "release" not in p.parts and not p.name.endswith(".pyc")]

def main():
    import yaml
    cfg = yaml.safe_load((ADDON / "config.yaml").read_text(encoding="utf-8"))
    if str(cfg["version"]) != VERSION:
        raise ValueError("config.yaml version and APP_VERSION differ")
    prefix = f"HA-UBOX-Bridge-{VERSION}"
    rootzip = RELEASE / f"{prefix}-addon-root.zip"
    repozip = RELEASE / f"{prefix}-repository.zip"
    allzip = RELEASE / f"{prefix}-complete.zip"
    make_zip(rootzip, [(p, p.relative_to(ADDON).as_posix()) for p in collect(ADDON)])
    make_zip(repozip, [(p, p.relative_to(ROOT).as_posix()) for p in collect(ROOT)])
    hashes = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
                     for p in (rootzip, repozip))
    manifest = RELEASE / "SHA256SUMS.txt"
    manifest.write_text(hashes, encoding="utf-8")
    with zipfile.ZipFile(allzip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in (rootzip, repozip, manifest):
            z.write(p, p.name)
    print("\n".join(f"{p.name}: {p.stat().st_size} bytes" for p in (rootzip, repozip, allzip)))

if __name__ == "__main__":
    main()
