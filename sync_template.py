"""Copy the files shared by the conference explorers into a sister repository.

This repository is the template source. Files in SHARED read every conference-specific
value from config.py; config.py, the scrapers and the README belong to each repository.
Edit shared files here, then sync:

    python sync_template.py ../cvpr-explorer          # overwrite the shared files there
    python sync_template.py ../cvpr-explorer --check  # exit 1 if any shared file differs
    python sync_template.py ../cvpr-explorer --test   # run its tests with these shared files
"""
import argparse
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile

SHARED = [
    "build_site.py",
    "embed.py",
    "layout.py",
    "sync_template.py",
    "templates/index.html",
    "pytest.ini",
    "requirements-dev.txt",
    "tests/test_build_site.py",
    "tests/test_layout.py",
    "tests/test_project_data.py",
    "tests/test_sync_template.py",
    ".github/workflows/ci.yml",
    ".github/workflows/pages.yml",
    ".github/dependabot.yml",
]


def stale(src, dst):
    """Shared files missing from dst or different from src."""
    # filecmp caches results by size and mtime, so a file rewritten within the same mtime tick reads as unchanged.
    filecmp.clear_cache()
    return [
        p for p in SHARED
        if not os.path.exists(os.path.join(dst, p))
        or not filecmp.cmp(os.path.join(src, p), os.path.join(dst, p), shallow=False)
    ]


def sync(src, dst):
    todo = stale(src, dst)
    for p in todo:
        os.makedirs(os.path.dirname(os.path.join(dst, p)), exist_ok=True)
        shutil.copyfile(os.path.join(src, p), os.path.join(dst, p))
    return todo


def trial(src, dst):
    """Exit code of dst's test suite run against src's shared files, in a scratch copy."""
    with tempfile.TemporaryDirectory() as tmp:
        copy = os.path.join(tmp, os.path.basename(os.path.abspath(dst)))
        shutil.copytree(dst, copy, ignore=shutil.ignore_patterns(
            ".git", ".venv", "__pycache__", ".pytest_cache", "site"))
        sync(src, copy)
        return subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=copy).returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", help="root of the repository to update")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="report differences, change nothing")
    mode.add_argument("--test", action="store_true",
                      help="run the target's tests with these shared files, change nothing")
    args = ap.parse_args()
    src = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(os.path.join(args.target, "config.py")):
        sys.exit(f"{args.target} has no config.py; create it before syncing.")
    if args.test:
        sys.exit(trial(src, args.target))

    todo = stale(src, args.target) if args.check else sync(src, args.target)
    for p in todo:
        print(("differs: " if args.check else "copied: ") + p)
    if not todo:
        print("shared files are in sync")
    if args.check and todo:
        sys.exit(1)


if __name__ == "__main__":
    main()
