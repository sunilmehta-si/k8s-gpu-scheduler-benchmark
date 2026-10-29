"""Compare the schedulers and tools pinned in cluster/versions.env with what upstream has released since.

The cluster runs measure exact releases, so a result says which KAI, Kueue or Volcano it came from. The cost is that
a pin only moves when someone looks. `gsb versions` looks: each pin, the latest release upstream and how far behind
the pin is. It reports; a bump stays a person's decision, because it can change the measured placements and the
cluster workflow has to show it.

A newer release counts as adoptable only once it is MIN_RELEASE_AGE_DAYS old: a broken or compromised release is
usually caught and withdrawn within days, and a benchmark gains nothing from being first.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "cluster" / "versions.env"
# The GitHub repository that publishes each pinned release. The node image is pinned by digest and is not compared.
COMPONENTS = {
    "KIND_VERSION": "kubernetes-sigs/kind",
    "KWOK_VERSION": "kubernetes-sigs/kwok",
    "KAI_VERSION": "kai-scheduler/KAI-Scheduler",
    "KUEUE_VERSION": "kubernetes-sigs/kueue",
    "VOLCANO_VERSION": "volcano-sh/volcano",
}
SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
MIN_RELEASE_AGE_DAYS = 14


class VersionsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Release:
    tag: str
    published: date | None = None


@dataclass(frozen=True)
class Row:
    name: str
    repo: str
    pinned: str
    latest: Release

    @property
    def status(self) -> str:
        return compare(self.pinned, self.latest.tag)

    @property
    def adoptable_on(self) -> date | None:
        if self.latest.published is None:
            return None
        return self.latest.published + timedelta(days=MIN_RELEASE_AGE_DAYS)

    def too_new(self, today: date) -> bool:
        return self.status != "current" and self.adoptable_on is not None and today < self.adoptable_on


def read_pins(path: Path = VERSIONS) -> dict[str, str]:
    pins = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            pins[key.strip()] = value.strip().strip('"')
    return pins


def compare(pinned: str, latest: str) -> str:
    """current, patch/minor/major behind, or 'unknown' when either side is not plain x.y.z."""
    a, b = SEMVER.match(pinned), SEMVER.match(latest)
    if not a or not b:
        return "current" if pinned.lstrip("v") == latest.lstrip("v") else "unknown"
    have, want = tuple(map(int, a.groups())), tuple(map(int, b.groups()))
    if have >= want:
        return "current"
    return "major behind" if have[0] < want[0] else "minor behind" if have[1] < want[1] else "patch behind"


def github_latest(repo: str) -> Release:
    """The repository's latest release through the API; GH_TOKEN or GITHUB_TOKEN raises the rate limit when set."""
    request = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                     headers={"Accept": "application/vnd.github+json", "User-Agent": "gsb-versions"})
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:   # noqa: S310 - fixed https API URL
            data = json.load(response)
        published = data.get("published_at")
        return Release(str(data["tag_name"]), datetime.fromisoformat(published.replace("Z", "+00:00")).date() if published else None)
    except (OSError, ValueError, KeyError) as exc:
        raise VersionsError(f"{repo}: could not read the latest release: {exc}") from exc


def report(pins: dict[str, str], fetch: Callable[[str], Release] | None = None) -> list[Row]:
    fetch = fetch or github_latest                  # looked up per call, so tests can patch github_latest
    missing = sorted(set(COMPONENTS) - set(pins))
    if missing:
        raise VersionsError(f"cluster/versions.env has no {', '.join(missing)}")
    return [Row(name, repo, pins[name], fetch(repo)) for name, repo in COMPONENTS.items()]


def markdown(rows: list[Row], today: date) -> str:
    behind = [r for r in rows if r.status != "current"]
    waiting = [r for r in behind if r.too_new(today)]
    lines = [f"## Pinned versions: {len(behind)} of {len(rows)} behind upstream"
             + (f", {len(waiting)} of them too new to adopt yet" if waiting else ""), "",
             "| Component | Pinned | Latest release | Status |", "|---|---|---|---|"]
    for r in rows:
        status = r.status
        if status != "current" and r.latest.published:
            status += f"; published {r.latest.published}, " + (f"adoptable from {r.adoptable_on}" if r.too_new(today) else "adoptable")
        lines.append(f"| {r.name} ([{r.repo}](https://github.com/{r.repo}/releases)) | {r.pinned} | {r.latest.tag} | {status} |")
    lines += ["", f"Releases are adopted once they are {MIN_RELEASE_AGE_DAYS} days old, so a broken or withdrawn release "
                  "has time to come to light first.", ""]
    return "\n".join(lines)


def as_json(rows: list[Row], today: date) -> str:
    """One object per pin, for tooling that wants to act on the drift rather than read about it."""
    return json.dumps([{"name": r.name, "repo": r.repo, "pinned": r.pinned, "latest": r.latest.tag,
                        "published": r.latest.published.isoformat() if r.latest.published else None,
                        "status": r.status, "adoptable_on": r.adoptable_on.isoformat() if r.adoptable_on else None,
                        "too_new": r.too_new(today)} for r in rows], indent=2) + "\n"
