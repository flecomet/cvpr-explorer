import sync_template


def make_tree(root, text):
    for p in sync_template.SHARED:
        f = root / p
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text + p)


def test_sync_copies_missing_and_changed_files(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    make_tree(src, "new ")
    make_tree(dst, "old ")
    (dst / sync_template.SHARED[0]).unlink()
    assert sync_template.stale(str(src), str(dst)) == sync_template.SHARED
    assert sync_template.sync(str(src), str(dst)) == sync_template.SHARED
    assert sync_template.stale(str(src), str(dst)) == []
    assert (dst / "layout.py").read_text() == "new layout.py"


def test_every_shared_file_exists_here():
    assert sync_template.stale(".", ".") == []


def make_consumer(tmp_path, assertion):
    src, dst = tmp_path / "src", tmp_path / "dst"
    for p in sync_template.SHARED:
        f = src / p
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("")
    (src / "pytest.ini").write_text("[pytest]\npythonpath = .\ntestpaths = tests\n")
    (dst / "tests").mkdir(parents=True)
    (dst / "config.py").write_text("")
    (dst / "tests" / "test_consumer.py").write_text(
        "import os\n\ndef test_consumer():\n    assert " + assertion + "\n")
    return src, dst


def test_trial_passes_when_consumer_tests_pass(tmp_path):
    src, dst = make_consumer(tmp_path, 'os.path.exists("templates/index.html")')
    assert sync_template.trial(str(src), str(dst)) == 0
    assert not (dst / "templates").exists()


def test_trial_fails_when_consumer_tests_fail(tmp_path):
    src, dst = make_consumer(tmp_path, "False")
    assert sync_template.trial(str(src), str(dst)) == 1
