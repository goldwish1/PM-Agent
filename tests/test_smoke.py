"""阶段 0 占位：包可导入、pytest 可运行。"""

from pm_agent import __version__


def test_package_version() -> None:
    assert __version__ == "0.1.0"
