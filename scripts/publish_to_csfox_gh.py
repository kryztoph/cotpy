#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse


PROJECT_DIR = Path(os.environ.get("COTPY_PROJECT_DIR", "/Users/fox/Private/Projects/cotpy"))
DEFAULT_REPO = "kryztoph/csfox-reports"
BRANCH = os.environ.get("COTPY_PUBLISH_BRANCH", "master")
TARGET_PREFIX = os.environ.get("COTPY_PUBLISH_PREFIX", "cotpy").strip("/")
DRY_RUN = os.environ.get("COTPY_PUBLISH_DRY_RUN", "0") == "1"
TRIGGER_PAGES = os.environ.get("COTPY_PUBLISH_TRIGGER_PAGES", "1") == "1"


TEXT_REPORTS = [
    Path("output/trade_setup_report.txt"),
    Path("output/position_summary.txt"),
]
CSV_REPORTS = [
    Path("output/position_summary.csv"),
    Path("output/positions.csv"),
    Path("output/signals.csv"),
    Path("output/market_summary.csv"),
]
DASHBOARD = Path("output/charts/dashboard.html")


def main() -> int:
    os.chdir(PROJECT_DIR)
    repo = _repo_name()
    files = _publish_files()
    generated = _index_html(files)
    generated["index.html"] = _site_index()

    if DRY_RUN:
        print(f"would publish cotpy reports to {repo}@{BRANCH}/{TARGET_PREFIX}")
        for source, target in files:
            print(f"  {source} -> {target}")
        for target in generated:
            print(f"  <generated> -> {target}")
        return 0

    ref = _gh_json(f"repos/{repo}/git/ref/heads/{BRANCH}")
    base_commit = cast(dict[str, Any], ref["object"])["sha"]
    commit_data = _gh_json(f"repos/{repo}/git/commits/{base_commit}")
    base_tree = cast(dict[str, Any], commit_data["tree"])["sha"]

    tree_entries = []
    for source, target in files:
        blob = _create_blob(repo, source.read_bytes())
        tree_entries.append(
            {
                "path": target,
                "mode": "100644",
                "type": "blob",
                "sha": blob["sha"],
            }
        )
    for target, content in generated.items():
        blob = _create_blob(repo, content.encode("utf-8"))
        tree_entries.append(
            {
                "path": target,
                "mode": "100644",
                "type": "blob",
                "sha": blob["sha"],
            }
        )

    tree = _gh_json(
        f"repos/{repo}/git/trees",
        method="POST",
        body={"base_tree": base_tree, "tree": tree_entries},
    )
    if tree["sha"] == base_tree:
        print("no cotpy report changes to commit")
        return 0

    commit = _gh_json(
        f"repos/{repo}/git/commits",
        method="POST",
        body={
            "message": "Update COT reports",
            "tree": tree["sha"],
            "parents": [base_commit],
        },
    )
    _gh_json(
        f"repos/{repo}/git/refs/heads/{BRANCH}",
        method="PATCH",
        body={"sha": commit["sha"], "force": False},
    )
    if TRIGGER_PAGES:
        try:
            _gh_json(f"repos/{repo}/pages/builds", method="POST")
            print("triggered GitHub Pages rebuild")
        except RuntimeError as exc:
            print(f"warning: could not trigger GitHub Pages rebuild: {exc}", file=sys.stderr)
    print(f"published cotpy reports to {repo}@{BRANCH}: {commit['sha']}")
    return 0


def _repo_name() -> str:
    explicit = os.environ.get("COTPY_PUBLISH_REPO")
    if explicit:
        return explicit
    url = os.environ.get("COTPY_PUBLISH_REPO_URL")
    if not url:
        return DEFAULT_REPO
    parsed = urlparse(url)
    if parsed.netloc:
        path = parsed.path.strip("/")
    else:
        path = url.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if path.count("/") != 1:
        raise ValueError(f"cannot parse GitHub repository from {url!r}")
    return path


def _publish_files() -> list[tuple[Path, str]]:
    required = [*TEXT_REPORTS, *CSV_REPORTS, DASHBOARD]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"missing {path}; regenerate reports first")

    chart_files = sorted(
        path
        for path in Path("output/charts").glob("*")
        if path.is_file() and path.name != ".DS_Store" and path.suffix.lower() in {".html", ".png"}
    )

    files: list[tuple[Path, str]] = []
    files.extend((path, f"{TARGET_PREFIX}/{path.name}") for path in TEXT_REPORTS)
    files.extend((path, f"{TARGET_PREFIX}/{path.name}") for path in CSV_REPORTS)
    files.extend((path, f"{TARGET_PREFIX}/charts/{path.name}") for path in chart_files)
    return files


def _index_html(files: list[tuple[Path, str]]) -> dict[str, str]:
    links = []
    for source, target in files:
        href = Path(target).name if "/charts/" not in target else f"charts/{Path(target).name}"
        label = source.name
        if source == DASHBOARD:
            label = "dashboard.html"
        links.append(f'      <li><a href="{href}">{label}</a></li>')

    content = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "  <head>",
            '    <meta charset="utf-8">',
            "    <title>COT Reports</title>",
            '    <meta name="viewport" content="width=device-width, initial-scale=1">',
            "  </head>",
            "  <body>",
            "    <h1>COT Reports</h1>",
            "    <p>Generated Commitments of Traders analysis reports.</p>",
            "    <ul>",
            *links,
            "    </ul>",
            "  </body>",
            "</html>",
            "",
        ]
    )
    return {f"{TARGET_PREFIX}/index.html": content}


def _site_index() -> str:
    """Create the repository-root landing page for GitHub Pages."""
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="0; url=cotpy/index.html">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>CSFox Reports</title>
  </head>
  <body>
    <p><a href="cotpy/index.html">Open CSFox reports</a></p>
  </body>
</html>
"""


def _create_blob(repo: str, content: bytes) -> dict[str, object]:
    encoded = base64.b64encode(content).decode("ascii")
    return _gh_json(
        f"repos/{repo}/git/blobs",
        method="POST",
        body={"content": encoded, "encoding": "base64"},
    )


def _gh_json(endpoint: str, method: str = "GET", body: dict[str, object] | None = None) -> dict[str, object]:
    cmd = [_gh_command(), "api", endpoint, "--method", method]
    input_data = None
    if body is not None:
        cmd.extend(["--input", "-"])
        input_data = json.dumps(body).encode("utf-8")
    completed = subprocess.run(cmd, input=input_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr.decode("utf-8", errors="replace"))
        raise RuntimeError(f"gh api failed: {' '.join(cmd)}")
    return json.loads(completed.stdout.decode("utf-8"))


def _gh_command() -> str:
    found = shutil.which("gh")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/gh", "/usr/local/bin/gh"):
        if Path(candidate).is_file():
            return candidate
    raise FileNotFoundError("gh CLI not found; install/authenticate gh or set PATH for launchd")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
