import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from gpu_sched_bench import versions
from gpu_sched_bench.cli import main
from gpu_sched_bench.versions import (COMPONENTS, NOT_COMPARED, Release, Row, VersionsError, compare, markdown, newest_ready,
                                      read_pins, report)

TODAY = date(2026, 10, 28)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args):
        return json.dumps(self.payload).encode()


def serving(routes):
    """A urlopen stand-in: the payload whose path ends the requested URL, else an unreachable API. Also returns the requests seen."""
    seen = []

    def urlopen(request, timeout=None):
        seen.append(request)
        for suffix, payload in routes.items():
            if request.full_url.endswith(suffix):
                return FakeResponse(payload)
        raise OSError(f"no route for {request.full_url}")
    return urlopen, seen


class CompareTests(unittest.TestCase):
    def test_how_far_behind(self):
        self.assertEqual(compare("0.18.6", "v0.18.6"), "current")        # KAI pins without the v its tags carry
        self.assertEqual(compare("v0.20.3", "v0.20.4"), "patch behind")
        self.assertEqual(compare("v1.16.0", "v1.17.0"), "minor behind")
        self.assertEqual(compare("v0.8.0", "v1.0.0"), "major behind")
        self.assertEqual(compare("v0.21.0", "v0.20.9"), "current")       # a pin ahead of "latest" is not behind
        self.assertEqual(compare("v1.0.0-rc.1", "v1.0.0"), "unknown")


class GithubApiTests(unittest.TestCase):
    LATEST = {"tag_name": "v1.2.3", "published_at": "2026-10-20T08:00:00Z"}
    LISTING = [LATEST]

    def read(self, routes, env=None):
        urlopen, seen = serving(routes)
        with mock.patch.dict(os.environ, env or {}, clear=True), mock.patch.object(versions.urllib.request, "urlopen", urlopen):
            return versions.github_latest("o/r"), seen

    def test_the_latest_release_carries_its_tag_and_publish_date(self):
        release, _ = self.read({"/repos/o/r/releases?per_page=50": self.LISTING})
        self.assertEqual(release, Release("v1.2.3", date(2026, 10, 20)))

    def test_a_release_candidate_marked_latest_is_not_the_latest_release(self):
        rc = {"tag_name": "v0.33.0rc3", "published_at": "2026-11-02T08:00:00Z", "prerelease": False}
        stable = {"tag_name": "v0.32.0", "published_at": "2026-10-18T08:00:00Z", "prerelease": False}
        older = {"tag_name": "v0.31.0", "published_at": "2026-10-05T08:00:00Z", "prerelease": False}
        release, _ = self.read({"/releases?per_page=50": [rc, stable, older]})
        self.assertEqual(release, Release("v0.32.0", date(2026, 10, 18)))

    def test_drafts_and_prereleases_are_skipped(self):
        listing = [{"tag_name": "v2.0.0", "published_at": "2026-10-30T08:00:00Z", "draft": True},
                   {"tag_name": "v1.9.0", "published_at": "2026-10-29T08:00:00Z", "prerelease": True},
                   {"tag_name": "v1.8.0", "published_at": "2026-10-01T08:00:00Z"}]
        release, _ = self.read({"/releases?per_page=50": listing})
        self.assertEqual(release.tag, "v1.8.0")

    def test_the_highest_version_wins_over_a_later_backport(self):
        listing = [{"tag_name": "v1.20.5", "published_at": "2026-11-01T08:00:00Z"},
                   {"tag_name": "v1.21.0", "published_at": "2026-10-20T08:00:00Z"}]
        release, _ = self.read({"/releases?per_page=50": listing})
        self.assertEqual(release.tag, "v1.21.0")

    def test_a_repository_without_a_plain_release_falls_back_to_the_latest_endpoint(self):
        listing = [{"tag_name": "release-2026.10", "published_at": "2026-10-01T08:00:00Z"}]
        release, seen = self.read({"/releases?per_page=50": listing, "/releases/latest": self.LATEST})
        self.assertEqual(release.tag, "v1.2.3")
        self.assertEqual(len(seen), 2)

    def test_the_stable_releases_come_highest_version_first(self):
        listing = [{"tag_name": "v0.20.4", "published_at": "2026-10-29T13:20:20Z"},
                   {"tag_name": "v0.20.5", "published_at": "2026-11-05T15:25:26Z"},
                   {"tag_name": "v0.21.0-rc.1", "published_at": "2026-11-08T08:00:00Z"},
                   {"tag_name": "v0.21.0", "published_at": "2026-11-09T08:00:00Z", "prerelease": True},
                   {"tag_name": "v0.20.3", "published_at": "2026-10-20T08:00:00Z"}]
        urlopen, _ = serving({"/releases?per_page=50": listing})
        with mock.patch.object(versions.urllib.request, "urlopen", urlopen):
            releases = versions.github_stable("o/r")
        self.assertEqual([r.tag for r in releases], ["v0.20.5", "v0.20.4", "v0.20.3"])
        self.assertEqual(releases[1].published, date(2026, 10, 29))
        urlopen, _ = serving({})
        with mock.patch.object(versions.urllib.request, "urlopen", urlopen):
            with self.assertRaisesRegex(VersionsError, "could not read the releases"):
                versions.github_stable("o/r")

    def test_an_unexpected_answer_is_a_versions_error(self):
        urlopen, _ = serving({"/releases?per_page=50": {"message": "Not Found"}})
        with mock.patch.object(versions.urllib.request, "urlopen", urlopen):
            with self.assertRaisesRegex(VersionsError, "latest release"):
                versions.github_latest("o/r")

    def test_a_token_raises_the_rate_limit_and_none_sends_no_header(self):
        _, seen = self.read({"/releases?per_page=50": self.LISTING}, env={"GH_TOKEN": "t0k"})
        self.assertEqual(seen[0].get_header("Authorization"), "Bearer t0k")
        _, seen = self.read({"/releases?per_page=50": self.LISTING})
        self.assertIsNone(seen[0].get_header("Authorization"))

    def test_the_release_notes_come_back_as_text(self):
        urlopen, _ = serving({"/releases/tags/v1.2.3": {"body": "notes"}})
        with mock.patch.object(versions.urllib.request, "urlopen", urlopen):
            self.assertEqual(versions.github_release_body("o/r", "v1.2.3"), "notes")

    def test_an_unreachable_api_is_a_versions_error_for_both_lookups(self):
        urlopen, _ = serving({})
        with mock.patch.object(versions.urllib.request, "urlopen", urlopen):
            with self.assertRaisesRegex(VersionsError, "latest release"):
                versions.github_latest("o/r")
            with self.assertRaisesRegex(VersionsError, "release notes"):
                versions.github_release_body("o/r", "v1.2.3")


class ReportTests(unittest.TestCase):
    def test_every_component_has_a_pin_in_versions_env(self):
        pins = read_pins()
        self.assertEqual(set(COMPONENTS) - set(pins), set())
        self.assertEqual(pins["KAI_VERSION"], "0.18.6")

    def test_every_pin_is_compared_or_says_why_not(self):
        # a new line in versions.env has to be mapped to the repository that releases it, or listed with its reason
        pins = read_pins()
        self.assertEqual(set(pins), set(COMPONENTS) | set(NOT_COMPARED))
        self.assertEqual(set(COMPONENTS) & set(NOT_COMPARED), set())

    def test_a_missing_pin_is_an_error_not_a_skipped_row(self):
        with self.assertRaisesRegex(VersionsError, "KWOK_VERSION"):
            report({k: "v1.0.0" for k in COMPONENTS if k != "KWOK_VERSION"}, fetch=lambda repo: Release("v1.0.0"))

    def test_rows_follow_the_component_order_and_use_the_fetched_release(self):
        rows = report({k: "v1.0.0" for k in COMPONENTS}, fetch=lambda repo: Release("v1.0.1", date(2026, 10, 1)))
        self.assertEqual([r.name for r in rows], list(COMPONENTS))
        self.assertEqual({r.status for r in rows}, {"patch behind"})

    def test_the_default_fetch_is_looked_up_when_called(self):
        with mock.patch.object(versions, "github_latest", return_value=Release("v1.0.0")) as fake:
            report({k: "v1.0.0" for k in COMPONENTS})
        self.assertEqual(fake.call_count, len(COMPONENTS))


class EarlierReleaseTests(unittest.TestCase):
    # Kueue on 12 Nov 2026: v0.20.5 (5 Nov) is too new, v0.20.4 (29 Oct) has just turned 14 days old
    KUEUE = [Release("v0.20.5", date(2026, 11, 5)), Release("v0.20.4", date(2026, 10, 29)), Release("v0.20.3", date(2026, 10, 20))]
    DAY = date(2026, 11, 12)

    def test_the_newest_release_past_the_pin_that_is_old_enough(self):
        self.assertEqual(newest_ready("v0.20.3", self.KUEUE, self.DAY), Release("v0.20.4", date(2026, 10, 29)))
        self.assertIsNone(newest_ready("v0.20.3", self.KUEUE, self.DAY - timedelta(days=1)))     # a day short of 14
        self.assertIsNone(newest_ready("v0.20.4", self.KUEUE, self.DAY))                         # nothing past the pin has aged
        self.assertIsNone(newest_ready("main", self.KUEUE, self.DAY))                            # a pin that is not x.y.z
        self.assertIsNone(newest_ready("v0.20.3", [Release("v0.20.4")], self.DAY))               # no date, no claim

    def test_report_looks_for_one_only_when_the_latest_is_too_new(self):
        seen = []
        def every(repo):
            seen.append(repo)
            return self.KUEUE
        pins = {k: "v0.20.3" for k in COMPONENTS}
        rows = report(pins, fetch=lambda repo: self.KUEUE[0], fetch_all=every, today=self.DAY)
        self.assertEqual(len(seen), len(COMPONENTS))
        self.assertEqual({r.ready.tag for r in rows}, {"v0.20.4"})
        self.assertTrue(all(r.too_new(self.DAY) and r.adoptable_now(self.DAY) for r in rows))
        seen.clear()
        rows = report(pins, fetch=lambda repo: self.KUEUE[0], fetch_all=every, today=date(2026, 11, 20))
        self.assertEqual(seen, [])                                                              # the latest itself is old enough
        self.assertEqual({r.ready for r in rows}, {None})

    def test_markdown_names_it_and_does_not_count_the_pin_as_waiting(self):
        row = Row("KUEUE_VERSION", "kubernetes-sigs/kueue", "v0.20.3", self.KUEUE[0], self.KUEUE[1])
        text = markdown([row], self.DAY)
        self.assertIn("| v0.20.3 | v0.20.5 | patch behind; published 2026-11-05, adoptable from 2026-11-19; "
                      "**v0.20.4** (published 2026-10-29) is adoptable now |", text)
        self.assertIn("1 of 1 behind upstream\n", text)


class MarkdownTests(unittest.TestCase):
    def row(self, pinned, tag, published):
        return Row("KUEUE_VERSION", "kubernetes-sigs/kueue", pinned, Release(tag, published))

    def test_a_release_younger_than_two_weeks_is_too_new(self):
        fresh = self.row("v0.20.3", "v0.20.4", date(2026, 10, 22))
        self.assertTrue(fresh.too_new(TODAY))
        self.assertEqual(fresh.adoptable_on, date(2026, 11, 5))
        text = markdown([fresh], TODAY)
        self.assertIn("1 of 1 behind upstream, 1 of them too new to adopt yet", text)
        self.assertIn("patch behind; published 2026-10-22, adoptable from 2026-11-05", text)

    def test_an_old_enough_release_is_adoptable_and_current_pins_say_so(self):
        old = self.row("v0.19.0", "v0.20.3", date(2026, 10, 1))
        self.assertFalse(old.too_new(TODAY))
        text = markdown([old, self.row("v0.20.3", "v0.20.3", date(2026, 10, 22))], TODAY)
        self.assertIn("1 of 2 behind upstream\n", text)
        self.assertIn("minor behind; published 2026-10-01, adoptable |", text)
        self.assertIn("| v0.20.3 | v0.20.3 | current |", text)
        self.assertIn("Not compared: KIND_NODE_IMAGE (pinned by digest", text)     # the reader sees what the table leaves out


class NodeImageTests(unittest.TestCase):
    NOTES = ("Images pre-built for this release:\n* v1.37.0: `kindest/node:v1.37.0@sha256:" + "a" * 64 + "`\n"
             "* v1.36.4: `kindest/node:v1.36.4@sha256:" + "b" * 64 + "`\n")

    def test_the_pinned_node_image_must_be_one_the_kind_release_lists(self):
        pins = {"KIND_VERSION": "v0.33.0", "KIND_NODE_IMAGE": "kindest/node:v1.37.0@sha256:" + "a" * 64}
        seen = []
        def body(repo, tag):
            seen.append((repo, tag)); return self.NOTES
        self.assertTrue(versions.node_image_listed(pins, body))
        self.assertEqual(seen, [("kubernetes-sigs/kind", "v0.33.0")])
        # the same tag with another digest was built for another release; the tag alone proves nothing
        pins["KIND_NODE_IMAGE"] = "kindest/node:v1.37.0@sha256:" + "c" * 64
        self.assertFalse(versions.node_image_listed(pins, body))

    def test_the_committed_pins_pass_against_the_real_notes_shape(self):
        pins = read_pins()
        notes = f"* {pins['KIND_NODE_IMAGE'].split(':')[1].split('@')[0]}: `{pins['KIND_NODE_IMAGE']}`"
        self.assertTrue(versions.node_image_listed(pins, lambda repo, tag: notes))

    def test_markdown_says_whether_the_node_image_is_listed(self):
        row = Row("KIND_VERSION", "kubernetes-sigs/kind", "v0.33.0", Release("v0.33.0", TODAY))
        self.assertIn("Node image: listed, digest and all", markdown([row], TODAY, node_image_ok=True))
        self.assertIn("**not among the images", markdown([row], TODAY, node_image_ok=False))
        self.assertNotIn("Node image:", markdown([row], TODAY))

    def test_cli_fails_when_the_node_image_is_not_listed(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(versions, "github_latest", return_value=Release("v0.33.0", date(2026, 1, 1))), \
                mock.patch.object(versions, "github_stable", return_value=[]), \
                mock.patch.object(versions, "github_release_body", return_value="nothing here"), \
                redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(main(["versions"]), 1)
        self.assertIn("not an image the pinned kind release lists", err.getvalue())


class CliTests(unittest.TestCase):
    def run_cli(self, *argv, published, stable=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(versions, "github_latest", return_value=Release("v9.9.9", published)), \
                mock.patch.object(versions, "github_stable", return_value=stable or []), \
                mock.patch.object(versions, "github_release_body", return_value=read_pins()["KIND_NODE_IMAGE"]), \
                redirect_stdout(out), redirect_stderr(err):
            code = main(["versions", *argv])
        return code, out.getvalue(), err.getvalue()

    def test_strict_fails_only_on_releases_old_enough_to_adopt(self):
        code, out, _ = self.run_cli("--strict", published=date.today() - timedelta(days=30))
        self.assertEqual(code, 1)
        self.assertIn("5 of 5 behind upstream", out)
        code, _, err = self.run_cli("--strict", published=date.today() - timedelta(days=3))
        self.assertEqual(code, 0)
        self.assertIn("too new to adopt yet: KIND_VERSION v9.9.9", err)

    def test_strict_fails_when_an_earlier_release_is_old_enough_though_the_latest_is_not(self):
        old = date.today() - timedelta(days=20)
        stable = [Release("v9.9.9", date.today() - timedelta(days=3)), Release("v9.9.8", old)]
        code, out, err = self.run_cli("--strict", published=date.today() - timedelta(days=3), stable=stable)
        self.assertEqual(code, 1)
        self.assertIn(f"**v9.9.8** (published {old}) is adoptable now", out)
        self.assertIn("KIND_VERSION v9.9.9 from", err)
        self.assertIn("(v9.9.8 is adoptable now)", err)

    def test_without_strict_it_only_reports(self):
        self.assertEqual(self.run_cli(published=date.today() - timedelta(days=30))[0], 0)

    def test_an_unreachable_api_is_an_error(self):
        with mock.patch.object(versions, "github_latest", side_effect=VersionsError("kubernetes-sigs/kind: offline")), \
                mock.patch.object(versions, "github_release_body", return_value=""), \
                redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(["versions"]), 2)
        self.assertIn("offline", err.getvalue())

    def test_json_rows_carry_the_dates_a_tool_needs(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = f"{d}/versions.json"
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(versions, "github_latest", return_value=Release("v9.9.9", date(2026, 10, 27))), \
                    mock.patch.object(versions, "github_stable", return_value=[]), \
                    mock.patch.object(versions, "github_release_body", return_value=read_pins()["KIND_NODE_IMAGE"]), \
                    redirect_stdout(out), redirect_stderr(err):
                self.assertEqual(main(["versions", "--json", path, "-o", f"{d}/versions.md"]), 0)
            rows = json.loads(Path(path).read_text())
        self.assertEqual([r["name"] for r in rows[:-1]], list(COMPONENTS))
        self.assertEqual(rows[-1], {"name": "KIND_NODE_IMAGE", "check": "listed in the pinned kind release's notes", "ok": True})
        rows = rows[:-1]
        self.assertEqual(rows[0]["latest"], "v9.9.9")
        self.assertEqual(rows[0]["adoptable_on"], "2026-11-10")
        self.assertEqual({r["status"] for r in rows}, {"major behind"})
        self.assertEqual({(r["ready"], r["ready_published"]) for r in rows}, {(None, None)})
        self.assertEqual(rows[0]["adoptable_now"], not rows[0]["too_new"])
