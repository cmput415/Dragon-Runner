"""
Unit tests for TestFile inline directive parsing.

Semantics under test:
  * CHECK:       one line of expected output (empty RHS = a blank line), joined
                 with '\n', no trailing newline.
  * CHECK_EMPTY: asserts the expected output is exactly empty (0 bytes); cannot be
                 combined with CHECK:/CHECK_FILE:.
"""
from dragon_runner.src.testfile import TestFile
from dragon_runner.src.errors import TestFileError as _TestFileError
from dragon_runner.src.runner import precise_diff


def _testfile(tmp_path, contents: str) -> TestFile:
    test_path = tmp_path / "case.in"
    test_path.write_text(contents)
    return TestFile(str(test_path))


def _expected_out(tmp_path, contents: str) -> bytes:
    return _testfile(tmp_path, contents).get_expected_out()


def test_check_lines_without_trailing_newline(tmp_path):
    out = _expected_out(tmp_path, "src\n//CHECK:5\n//CHECK:7\n")
    assert out == b"5\n7"


def test_trailing_empty_check_encodes_trailing_newline(tmp_path):
    # a trailing empty //CHECK: (NOT //CHECK_EMPTY:) encodes the terminating newline
    out = _expected_out(tmp_path, "src\n//CHECK:5\n//CHECK:7\n//CHECK:\n")
    assert out == b"5\n7\n"


def test_empty_check_encodes_blank_line_in_middle(tmp_path):
    out = _expected_out(tmp_path, "src\n//CHECK:a\n//CHECK:\n//CHECK:b\n")
    assert out == b"a\n\nb"


def test_check_empty_asserts_zero_byte_output(tmp_path):
    out = _expected_out(tmp_path, "src\n//CHECK_EMPTY:\n")
    assert out == b""


def test_no_directives_is_empty_output(tmp_path):
    out = _expected_out(tmp_path, "just source\n")
    assert out == b""


def test_check_rhs_is_literal_including_leading_space(tmp_path):
    out = _expected_out(tmp_path, "src\n//CHECK: 5\n")
    assert out == b" 5"


def test_check_empty_not_matched_as_check(tmp_path):
    # CHECK_EMPTY: must be invisible to the CHECK: scan (order preserved).
    out = _expected_out(tmp_path, "src\n//CHECK:9\n//CHECK:8\n")
    assert out == b"9\n8"


def test_check_empty_conflicts_with_check(tmp_path):
    tf = _testfile(tmp_path, "src\n//CHECK:5\n//CHECK_EMPTY:\n")
    assert isinstance(tf.expected_out, _TestFileError)
    assert tf.verify().errors  # surfaced during verification


def test_check_empty_conflicts_with_check_file(tmp_path):
    tf = _testfile(tmp_path, "src\n//CHECK_FILE:./out.txt\n//CHECK_EMPTY:\n")
    assert isinstance(tf.expected_out, _TestFileError)


def test_trailing_newline_output_matches_via_trailing_empty_check(tmp_path):
    # A program that terminates each line with a newline (as the fuzzers'
    # interpreters do) matches expected output built with a trailing empty //CHECK:.
    expected = _expected_out(tmp_path, "src\n//CHECK:5\n//CHECK:7\n//CHECK:\n")
    assert precise_diff(b"5\n7\n", expected) == ""


def test_custom_comment_prefix(tmp_path):
    test_path = tmp_path / "case.in"
    test_path.write_text("src\n#CHECK:hi\n#CHECK:\n")
    # a non-default comment prefix recognizes directives introduced by that prefix
    assert TestFile(str(test_path), comment_syntax="#").get_expected_out() == b"hi\n"
    # while the default // prefix does not see the # directives
    assert TestFile(str(test_path)).get_expected_out() == b""
