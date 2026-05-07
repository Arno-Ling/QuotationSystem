"""Unit test for mvp.rules."""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from mvp.rules import suggest_decision


def test_forced_outsource():
    for p in ("热处理", "表面处理", "线割"):
        s = suggest_decision(p)
        assert s.decision == "outsource", f"{p} should be outsource"
        assert s.is_forced is True
        assert p in s.reason


def test_internal_processes():
    for p in ("磨", "铣", "车", "钻", "镗"):
        s = suggest_decision(p)
        assert s.decision == "self_made", f"{p} should be self_made"
        assert s.is_forced is False


def test_fuzzy_internal_match():
    # 包含关键词的复合工艺
    s = suggest_decision("精磨")
    assert s.decision == "self_made"
    assert "磨" in s.reason


def test_unknown_defaults_to_outsource():
    s = suggest_decision("激光切割")
    assert s.decision == "outsource"
    assert s.is_forced is False


def test_empty_process():
    s = suggest_decision("")
    assert s.decision == "outsource"


if __name__ == "__main__":
    test_forced_outsource()
    test_internal_processes()
    test_fuzzy_internal_match()
    test_unknown_defaults_to_outsource()
    test_empty_process()
    print("[OK] All rules tests passed")
