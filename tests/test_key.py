import sys, tempfile, textwrap
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from key import Key, StudentRecord

CSV = textwrap.dedent("""\
    SID,CCID,GitHubID,A1,A2
    1234567,alice,alice-gh,team-alpha,opt-alpha
    1234568,bob,bob-gh,team-alpha,opt-beta
    1234569,carol,carol-gh,team-beta,,
""")

def make_key(csv_text=CSV):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    f.write(csv_text)
    f.close()
    return Key(Path(f.name))

def test_assignments():
    assert make_key().assignments == ["A1", "A2"]

def test_lookup_by_sid():
    assert make_key().get("1234567").ccid == "alice"

def test_lookup_by_ccid():
    assert make_key().get("bob").sid == "1234568"

def test_lookup_by_github():
    assert make_key().get("carol-gh").sid == "1234569"

def test_lookup_miss():
    assert make_key().get("nobody") is None

def test_iter_repos_unique():
    assert sorted(make_key().iter_repos("A1")) == ["team-alpha", "team-beta"]

def test_iter_repos_skips_empty():
    assert sorted(make_key().iter_repos("A2")) == ["opt-alpha", "opt-beta"]

def test_students_for_repo_team():
    members = make_key().students_for_repo("A1", "team-alpha")
    assert [m.sid for m in members] == ["1234567", "1234568"]

def test_get_repo():
    k = make_key()
    assert k.get_repo("carol", "A1") == "team-beta"
    assert k.get_repo("carol", "A2") is None

def test_iter_students_count():
    assert len(list(make_key().iter_students())) == 3
