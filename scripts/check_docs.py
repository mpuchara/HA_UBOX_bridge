"""Check internal documentation links and required current entry points.

This checks Markdown link targets in the Git repo, not network destinations.
Historical CHANGELOG entries are intentionally not treated as instructions.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
files = sorted(ROOT.rglob("*.md"))
errors = []
links_checked = 0

for source in files:
    if ".git" in source.parts or "release" in source.parts:
        continue
    text = source.read_text(encoding="utf-8")
    for reference in re.findall(r"\]\(([^)\s]+)(?:\s+[^)]*)?\)", text):
        if reference.startswith(("http:", "https:", "mailto:", "#")):
            continue
        fragmentless = reference.partition("#")[0]
        if not fragmentless:
            continue
        target = (source.parent / fragmentless).resolve()
        links_checked += 1
        if not target.is_relative_to(ROOT) or not target.is_file():
            errors.append(f"{source.relative_to(ROOT)}: dead link -> {reference}")
    if source.name == "README.md" and source.parent == ROOT:
        for file_name in ("docs/INSTALL_HA.md", "docs/CYD_WEB_INSTALL.md",
                          "docs/ANDROID_WIDGET.md", "docs/TROUBLESHOOTING.md",
                          "docs/USER_GUIDE.md", "docs/SECURITY.md"):
            if not (ROOT / file_name).exists():
                errors.append(f"Missing primary manual: {file_name}")

version = (ROOT / "ubox_bridge" / "APP_VERSION").read_text().strip()
config = (ROOT / "ubox_bridge" / "config.yaml").read_text()
if f'version: "{version}"' not in config:
    errors.append("APP_VERSION does not match add-on config.yaml")
if not (ROOT / "web-installer" / "manifest-ili9341.json").exists():
    errors.append("Missing ILI9341 installer manifest")
if errors:
    sys.exit("\n".join(errors))
print(f"Documentation verified: {len(files)} Markdown files, {links_checked} internal links; add-on v{version}")
