"""Compare the schedulers and tools pinned in cluster/versions.env with what upstream has released since.

The cluster runs measure exact releases, so a result says which KAI, Kueue or Volcano it came from. The cost is that
a pin only moves when someone looks. `gsb versions` looks: each pin, the latest release upstream and how far behind
the pin is. It reports; a bump stays a person's decision, because it can change the measured placements and the
cluster workflow has to show it.

A newer release counts as adoptable only once it is MIN_RELEASE_AGE_DAYS old: a broken or compromised release is
usually caught and withdrawn within days, and a benchmark gains nothing from being first. When the newest release is
too new, an earlier one past the pin may already be old enough (Kueue v0.20.4 while v0.20.5 waits), and the report
names it, so a fix that has aged is not held back by the one released after it.
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
# The GitHub repository that publishes each pinned release.
COMPONENTS = {
    "KIND_VERSION": "kubernetes-sigs/kind",
    "KWOK_VERSION": "kubernetes-sigs/kwok",
    "KAI_VERSION": "kai-scheduler/KAI-Scheduler",
    "KUEUE_VERSION": "kubernetes-sigs/kueue",
    "VOLCANO_VERSION": "volcano-sh/volcano",
}
# Pins that are not releases to compare, and why. Every line in versions.env is in COMPONENTS or here, so a new pin
# has to say which it is.
NOT_COMPARED = {
    "KIND_NODE_IMAGE": "pinned by digest and chosen from the kind release's notes, which list the node images built for it",
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
    # The newest release past the pin that is already old enough, when the latest is not.
    ready: Release | None = None

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

    def adoptable_now(self, today: date) -> bool:
        """A release past the pin can be taken today: the latest, or an earlier one when the latest is too new."""
        return self.status != "current" and (not self.too_new(today) or self.ready is not None)


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


def _github_json(path: str) -> object:
    """One GitHub API GET; GH_TOKEN or GITHUB_TOKEN raises the rate limit when set."""
    request = urllib.request.Request(f"https://api.github.com/{path}",
                                     headers={"Accept": "application/vnd.github+json", "User-Agent": "gsb-versions"})
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=20) as response:   # noqa: S310 - fixed https API URL
        return json.load(response)


def _release(data: dict) -> Release:
    published = data.get("published_at")
    return Release(str(data["tag_name"]), datetime.fromisoformat(published.replace("Z", "+00:00")).date() if published else None)


def _semver(tag: str) -> tuple[int, int, int]:
    return tuple(map(int, SEMVER.match(tag).groups()))


def _stable_listing(repo: str) -> list[dict]:
    """The newest 50 releases that are published, not drafts or prereleases, and plain x.y.z."""
    listing = _github_json(f"repos/{repo}/releases?per_page=50")
    if not isinstance(listing, list):
        raise ValueError("expected a list of releases")
    return [r for r in listing if not r.get("draft") and not r.get("prerelease") and SEMVER.match(str(r.get("tag_name")))]


def github_stable(repo: str) -> list[Release]:
    """Every stable release among the newest 50, highest version first."""
    try:
        return [_release(r) for r in sorted(_stable_listing(repo), key=lambda r: _semver(r["tag_name"]), reverse=True)]
    except (OSError, ValueError, KeyError) as exc:
        raise VersionsError(f"{repo}: could not read the releases: {exc}") from exc


def newest_ready(pinned: str, releases: list[Release], today: date) -> Release | None:
    """The highest release past the pin that is MIN_RELEASE_AGE_DAYS old by today, if any."""
    if not SEMVER.match(pinned):
        return None
    old_enough = [r for r in releases if SEMVER.match(r.tag) and _semver(r.tag) > _semver(pinned) and r.published
                  and r.published + timedelta(days=MIN_RELEASE_AGE_DAYS) <= today]
    return max(old_enough, key=lambda r: _semver(r.tag), default=None)


def github_latest(repo: str) -> Release:
    """The newest stable release: the highest plain x.y.z among published, non-draft, non-prerelease releases.

    GitHub's `releases/latest` returns whatever the maintainers mark latest, and some projects mark their release
    candidates (vLLM's v0.33.0rc3), which neither compares with a pin nor is anything to adopt. The same call that
    lists the releases shows the stable ones. A repository with no plain x.y.z release falls back to
    `releases/latest`."""
    try:
        stable = _stable_listing(repo)
        if stable:
            return _release(max(stable, key=lambda r: _semver(r["tag_name"])))
        return _release(_github_json(f"repos/{repo}/releases/latest"))
    except (OSError, ValueError, KeyError) as exc:
        raise VersionsError(f"{repo}: could not read the latest release: {exc}") from exc


def github_release_body(repo: str, tag: str) -> str:
    """The release notes of one tag through the API."""
    try:
        return str(_github_json(f"repos/{repo}/releases/tags/{tag}").get("body") or "")
    except (OSError, ValueError) as exc:
        raise VersionsError(f"{repo} {tag}: could not read the release notes: {exc}") from exc


def node_image_listed(pins: dict[str, str], fetch_body: Callable[[str, str], str] | None = None) -> bool:
    """True when the pinned node image, digest included, is one the pinned kind release's notes list.

    kind builds node images per release and says to use them by digest; a node image from another release can
    start, and fail in ways that look like the scheduler under test. The notes list every image as
    `kindest/node:<k8s>@sha256:<digest>`, so the check is that exact string."""
    fetch_body = fetch_body or github_release_body
    return pins["KIND_NODE_IMAGE"] in fetch_body(COMPONENTS["KIND_VERSION"], pins["KIND_VERSION"])


def report(pins: dict[str, str], fetch: Callable[[str], Release] | None = None,
           fetch_all: Callable[[str], list[Release]] | None = None, today: date | None = None) -> list[Row]:
    """One row per component. Only when the latest release is too new are the earlier ones listed, to find one
    that is old enough: one more API call, for the few pins that need it."""
    fetch = fetch or github_latest                  # looked up per call, so tests can patch github_latest
    fetch_all = fetch_all or github_stable
    today = today or date.today()
    missing = sorted(set(COMPONENTS) - set(pins))
    if missing:
        raise VersionsError(f"cluster/versions.env has no {', '.join(missing)}")
    rows = []
    for name, repo in COMPONENTS.items():
        row = Row(name, repo, pins[name], fetch(repo))
        if row.too_new(today):
            row = Row(name, repo, row.pinned, row.latest, newest_ready(row.pinned, fetch_all(repo), today))
        rows.append(row)
    return rows


def markdown(rows: list[Row], today: date, node_image_ok: bool | None = None) -> str:
    behind = [r for r in rows if r.status != "current"]
    waiting = [r for r in behind if r.too_new(today) and r.ready is None]
    lines = [f"## Pinned versions: {len(behind)} of {len(rows)} behind upstream"
             + (f", {len(waiting)} of them too new to adopt yet" if waiting else ""), "",
             "| Component | Pinned | Latest release | Status |", "|---|---|---|---|"]
    for r in rows:
        status = r.status
        if status != "current" and r.latest.published:
            status += f"; published {r.latest.published}, " + (f"adoptable from {r.adoptable_on}" if r.too_new(today) else "adoptable")
            if r.too_new(today) and r.ready:
                status += f"; **{r.ready.tag}** (published {r.ready.published}) is adoptable now"
        lines.append(f"| {r.name} ([{r.repo}](https://github.com/{r.repo}/releases)) | {r.pinned} | {r.latest.tag} | {status} |")
    lines += ["", f"Releases are adopted once they are {MIN_RELEASE_AGE_DAYS} days old, so a broken or withdrawn release "
                  "has time to come to light first."]
    lines += ["", "Not compared: " + "; ".join(f"{name} ({why})" for name, why in NOT_COMPARED.items()) + "."]
    if node_image_ok is not None:
        lines += ["", "Node image: " + ("listed, digest and all, in the pinned kind release's notes." if node_image_ok else
                  "**not among the images the pinned kind release's notes list**: it was built for another kind release.")]
    lines.append("")
    return "\n".join(lines)


def as_json(rows: list[Row], today: date, node_image_ok: bool | None = None) -> str:
    """One object per pin, for tooling that wants to act on the drift rather than read about it; the node image check
    rides along as a final object when it ran, so a tool reads one file for everything the report knows."""
    out = [{"name": r.name, "repo": r.repo, "pinned": r.pinned, "latest": r.latest.tag,
            "published": r.latest.published.isoformat() if r.latest.published else None,
            "status": r.status, "adoptable_on": r.adoptable_on.isoformat() if r.adoptable_on else None,
            "too_new": r.too_new(today), "adoptable_now": r.adoptable_now(today),
            "ready": r.ready.tag if r.ready else None,
            "ready_published": r.ready.published.isoformat() if r.ready and r.ready.published else None} for r in rows]
    if node_image_ok is not None:
        out.append({"name": "KIND_NODE_IMAGE", "check": "listed in the pinned kind release's notes", "ok": node_image_ok})
    return json.dumps(out, indent=2) + "\n"
