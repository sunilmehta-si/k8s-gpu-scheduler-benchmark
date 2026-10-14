import io
import unittest
from contextlib import redirect_stdout

from gpu_sched_bench import __version__
from gpu_sched_bench.cli import main


class CliTests(unittest.TestCase):
    def test_version(self):
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit) as exit_:
            main(["--version"])
        self.assertEqual(exit_.exception.code, 0)
        self.assertIn(__version__, buf.getvalue())

    def test_help_without_command(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main([]), 0)
