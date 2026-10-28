import unittest
from datetime import date
from unittest import mock

from gpu_sched_bench import versions
from gpu_sched_bench.versions import COMPONENTS, Release, Row, VersionsError, compare, markdown, read_pins, report

TODAY = date(2026, 10, 28)


class CompareTests(unittest.TestCase):
    def test_how_far_behind(self):
        self.assertEqual(compare("0.18.6", "v0.18.6"), "current")        # KAI pins without the v its tags carry
        self.assertEqual(compare("v0.20.3", "v0.20.4"), "patch behind")
        self.assertEqual(compare("v1.16.0", "v1.17.0"), "minor behind")
        self.assertEqual(compare("v0.8.0", "v1.0.0"), "major behind")
        self.assertEqual(compare("v0.21.0", "v0.20.9"), "current")       # a pin ahead of "latest" is not behind
        self.assertEqual(compare("v1.0.0-rc.1", "v1.0.0"), "unknown")


class ReportTests(unittest.TestCase):
    def test_every_component_has_a_pin_in_versions_env(self):
        pins = read_pins()
        self.assertEqual(set(COMPONENTS) - set(pins), set())
        self.assertEqual(pins["KAI_VERSION"], "0.18.6")

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
