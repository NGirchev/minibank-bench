#!/usr/bin/env python3
"""Grade an agent's attempt at one of the agent tasks.

Usage:
  grade.py TASK REPO_DIR      grade a finished attempt, print JSON
  grade.py TASK --selfcheck   validate the task: reference passes, every mutant is a real bug

A task directory holds task.json, fixture/ (what the agent gets), reference/
(files overlaid on the fixture to make the correct solution), hidden/ (the
acceptance tests) and mutants.py (wrong fixes for scoring the agent's tests).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent / "tasks"
MARK = "__RESULT__"

RUNNER = r'''
import importlib.util, json, os, sys, unittest
root, mode = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
os.chdir(root)
loader = unittest.TestLoader()
if mode == "discover":
    suite = unittest.TestSuite()
    for pattern in ("test*.py", "*_test.py"):
        for test in loader.discover(root, pattern=pattern, top_level_dir=root):
            suite.addTest(test)
else:
    spec = importlib.util.spec_from_file_location("hidden_tests", sys.argv[3])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    suite = loader.loadTestsFromTestCase(getattr(mod, sys.argv[4]))

class Result(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.out = {}
    def addSuccess(self, test):
        self.out.setdefault(test.id(), "pass")
    def addFailure(self, test, err):
        self.out[test.id()] = "fail"
    def addError(self, test, err):
        self.out[test.id()] = "error"
    def addSkip(self, test, reason):
        self.out.setdefault(test.id(), "skip")
    def addExpectedFailure(self, test, err):
        self.out.setdefault(test.id(), "pass")
    def addUnexpectedSuccess(self, test):
        self.out[test.id()] = "fail"
    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.out[test.id()] = "fail"

result = Result()
suite.run(result)
print("__RESULT__" + json.dumps(result.out))
'''


class Task:
    def __init__(self, name: str):
        self.name = name
        self.dir = HERE / name
        self.cfg = json.loads((self.dir / "task.json").read_text())
        self.package = self.cfg["package"]
        self.fixture = self.dir / "fixture"
        self.hidden = self.dir / "hidden" / "test_hidden.py"
        spec = importlib.util.spec_from_file_location(f"mutants_{name}", self.dir / "mutants.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.mutants: dict = mod.MUTANTS

    def reference_package(self, dest: Path) -> Path:
        shutil.copytree(self.fixture / self.package, dest, ignore=shutil.ignore_patterns("__pycache__"))
        for src in (self.dir / "reference" / self.package).glob("*.py"):
            shutil.copy(src, dest / src.name)
        return dest

    def mutant_package(self, name: str, dest: Path) -> Path:
        self.reference_package(dest)
        file, old, new = self.mutants[name]
        path = dest / file
        text = path.read_text()
        if old not in text:
            raise RuntimeError(f"mutant {name}: anchor not found in {file}")
        path.write_text(text.replace(old, new, 1))
        return dest

    def with_package(self, repo: Path, package: Path, dest: Path) -> Path:
        shutil.copytree(repo, dest, ignore=shutil.ignore_patterns("__pycache__", ".git"))
        shutil.rmtree(dest / self.package, ignore_errors=True)
        shutil.copytree(package, dest / self.package, ignore=shutil.ignore_patterns("__pycache__"))
        return dest


def run_tests(root: Path, mode: str, *extra: str, timeout: int = 120) -> dict[str, str] | None:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(RUNNER)
        runner = fh.name
    try:
        proc = subprocess.run([sys.executable, "-I", runner, str(root), mode, *extra], cwd=root,
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    finally:
        Path(runner).unlink(missing_ok=True)
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith(MARK):
            return json.loads(line[len(MARK):])
    return {}


def hidden_results(task: Task, repo: Path) -> dict[str, str]:
    def one(cls: str) -> dict[str, str]:
        res = run_tests(repo, "file", str(task.hidden), cls, timeout=90)
        if res is None:
            return {f"timeout.{cls}.all": "timeout"}
        return res or {f"crash.{cls}.all": "error"}
    out: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for res in pool.map(one, task.cfg["hidden_classes"]):
            out.update(res)
    return out


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def grade(task: Task, repo: Path) -> dict:
    hidden = hidden_results(task, repo)
    passed = sum(1 for v in hidden.values() if v == "pass")
    subtle = {k: v for k, v in hidden.items() if ".test_subtle_" in k}
    by_class: dict[str, list[int]] = {}
    for test_id, status in hidden.items():
        cls = test_id.split(".")[-2]
        by_class.setdefault(cls, [0, 0])
        by_class[cls][0] += status == "pass"
        by_class[cls][1] += 1

    given = set(task.cfg["given_test_ids"])
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ref_pkg = task.reference_package(tmp / "ref-pkg")
        on_ref = run_tests(task.with_package(repo, ref_pkg, tmp / "ref"), "discover") or {}
        own = {k: v for k, v in on_ref.items() if k not in given}
        trusted = {k for k, v in own.items() if v == "pass"}
        contradicting = sorted(k for k, v in own.items() if v != "pass")

        def killed(name: str) -> bool:
            root = task.with_package(repo, task.mutant_package(name, tmp / f"pkg-{name}"), tmp / f"m-{name}")
            res = run_tests(root, "discover")
            return True if res is None else any(res.get(t) != "pass" for t in trusted)

        if trusted:
            with ThreadPoolExecutor(max_workers=6) as pool:
                kills = dict(zip(task.mutants, pool.map(killed, task.mutants)))
        else:
            kills = {name: False for name in task.mutants}
        visible = run_tests(repo, "discover") or {}

    rules = {f"unchanged:{p}": digest(repo / p) == digest(task.fixture / p) for p in task.cfg["protected"]}
    rules["given_tests_pass"] = all(visible.get(t) == "pass" for t in task.cfg["given_must_pass"])
    pinned = task.cfg.get("pinned")
    if pinned:
        test_id = pinned["test_id"]
        module = test_id.rsplit(".", 2)[0]
        same_file = [k for k in on_ref if k.startswith(module + ".")]
        if test_id in on_ref:
            rules["pinned_test_updated"] = on_ref[test_id] == "pass"
        else:  # renamed or rewritten: the file must still hold passing tests
            rules["pinned_test_updated"] = len(same_file) >= 2 and all(on_ref[k] == "pass" for k in same_file)

    hidden_score = passed / max(len(hidden), 1)
    subtle_score = sum(v == "pass" for v in subtle.values()) / max(len(subtle), 1)
    kill_score = sum(kills.values()) / len(kills)
    rules_score = sum(rules.values()) / len(rules)
    return {
        "score": round(0.5 * hidden_score + 0.15 * subtle_score + 0.25 * kill_score + 0.1 * rules_score, 3),
        "hidden": {"passed": passed, "total": len(hidden), "by_class": by_class,
                   "failed": sorted(k.split(".", 1)[1] for k, v in hidden.items() if v != "pass")},
        "subtle": {"passed": sum(v == "pass" for v in subtle.values()), "total": len(subtle),
                   "failed": sorted(k.split(".")[-1] for k, v in subtle.items() if v != "pass")},
        "own_tests": {"count": len(own), "spec_conflicting": contradicting},
        "mutants": {"killed": sum(kills.values()), "total": len(kills),
                    "survived": sorted(k for k, v in kills.items() if not v)},
        "rules": rules,
    }


def selfcheck(task: Task) -> int:
    ok = True
    root = Path(tempfile.mkdtemp())
    try:
        ref_repo = task.with_package(task.fixture, task.reference_package(root / "ref-pkg"), root / "repo")
        res = hidden_results(task, ref_repo)
        bad = [k for k, v in res.items() if v != "pass"]
        print(f"reference: {len(res) - len(bad)}/{len(res)} hidden pass", "OK" if not bad else bad)
        ok &= not bad
        for name in task.mutants:
            m_repo = task.with_package(task.fixture, task.mutant_package(name, root / f"pkg-{name}"), root / f"m-{name}")
            res = hidden_results(task, m_repo)
            failing = [k.split(".")[-1] for k, v in res.items() if v != "pass"]
            print(f"mutant {name}: {len(failing)} hidden fail", "" if failing else "NOT A BUG")
            ok &= bool(failing)
        res = hidden_results(task, task.fixture)
        print(f"fixture: {sum(v == 'pass' for v in res.values())}/{len(res)} hidden pass")
        given = run_tests(task.fixture, "discover") or {}
        missing = [t for t in task.cfg["given_test_ids"] if given.get(t) != "pass"]
        print("fixture given tests:", "all pass" if not missing else f"failing {missing}")
        ok &= not missing
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    task = Task(sys.argv[1])
    if sys.argv[2] == "--selfcheck":
        sys.exit(selfcheck(task))
    print(json.dumps(grade(task, Path(sys.argv[2]).resolve()), indent=1, ensure_ascii=False))
