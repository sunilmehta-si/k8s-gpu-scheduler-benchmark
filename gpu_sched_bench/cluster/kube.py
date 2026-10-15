"""A thin kubectl wrapper. Using the CLI (not a client library) keeps the dependency list at PyYAML and means the
benchmark talks to the cluster exactly the way an operator would, with the same kubeconfig and context."""
from __future__ import annotations

import json
import subprocess


class KubeError(RuntimeError):
    pass


class Kubectl:
    def __init__(self, context: str | None = None, binary: str = "kubectl", timeout: int = 120):
        self.base = [binary] + (["--context", context] if context else [])
        self.timeout = timeout

    def run(self, *args: str, stdin: str | None = None) -> str:
        try:
            proc = subprocess.run([*self.base, *args], input=stdin, capture_output=True, text=True, timeout=self.timeout)
        except FileNotFoundError as exc:
            raise KubeError(f"{self.base[0]} not found; install kubectl or pass --kubectl") from exc
        except subprocess.TimeoutExpired as exc:
            raise KubeError(f"kubectl {' '.join(args[:3])} timed out after {self.timeout}s") from exc
        if proc.returncode != 0:
            raise KubeError(f"kubectl {' '.join(args[:3])} failed: {proc.stderr.strip()[:400]}")
        return proc.stdout

    def apply(self, manifest_yaml: str, server_side: bool = False) -> str:
        args = ["apply", "-f", "-"] + (["--server-side", "--force-conflicts"] if server_side else [])
        return self.run(*args, stdin=manifest_yaml)

    def get_json(self, *args: str) -> dict:
        out = self.run("get", *args, "-o", "json")
        try:
            return json.loads(out)
        except ValueError as exc:
            raise KubeError(f"kubectl get {' '.join(args)} returned invalid JSON") from exc


class FakeKubectl:
    """Records applies and answers `get` from canned objects; used by tests and dry runs."""

    def __init__(self, objects: dict[str, dict] | None = None):
        self.applied: list[str] = []
        self.objects = objects or {}

    def apply(self, manifest_yaml: str, server_side: bool = False) -> str:
        self.applied.append(manifest_yaml)
        return ""

    def get_json(self, *args: str) -> dict:
        return self.objects.get(args[0], {"items": []})
