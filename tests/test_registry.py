from __future__ import annotations

from pathlib import Path

import pytest

from josseph.metrics.registry import ExtractorFactoryContext, ExtractorRegistry
from josseph.pipeline.extractor_factory import select_extractors


class DummyRunner:
    def run(self, cmd, *, cwd=None, env=None, timeout=None):
        return ""


def make_registry(tmp_path, monkeypatch, *, settings_by_name=None):
    package_name = "tmp_registry_extractors"
    package_dir = tmp_path / package_name
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    for name in ("ck", "cm", "github", "sonar"):
        (package_dir / f"{name}.py").write_text(
            "\n".join(
                [
                    f'EXTRACTOR_NAME = "{name}"',
                    "",
                    "class DummyExtractor:",
                    "    requires_checkout = True",
                    "",
                    "    def __init__(self, settings=None):",
                    "        self.settings = settings or {}",
                    "",
                    "    def run(self, target):",
                    "        return []",
                    "",
                    "def build_extractor(context, settings):",
                    "    return DummyExtractor(settings)",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    monkeypatch.syspath_prepend(str(tmp_path))
    return ExtractorRegistry(
        ExtractorFactoryContext(
            third_party_path=Path("."),
            env={},
            command_runner=DummyRunner(),
        ),
        package_name=package_name,
        settings_by_name=settings_by_name,
    )


def test_registry_exposes_expected_extractor_names(tmp_path, monkeypatch):
    registry = make_registry(tmp_path, monkeypatch)

    created = registry.create_all()

    assert registry.names() == ["ck", "cm", "github", "sonar"]
    assert set(created) == {"ck", "cm", "github", "sonar"}


def test_registry_caches_created_extractors(tmp_path, monkeypatch):
    registry = make_registry(tmp_path, monkeypatch)

    first = registry.get("github")
    second = registry.get("github")

    assert first is second


def test_registry_passes_per_extractor_settings(tmp_path, monkeypatch):
    registry = make_registry(
        tmp_path,
        monkeypatch,
        settings_by_name={"github": {"token": "abc"}},
    )

    extractor = registry.get("github")

    assert extractor.settings == {"token": "abc"}


def test_extractor_factory_rejects_unknown_tool(tmp_path, monkeypatch):
    registry = make_registry(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="Unknown tool\\(s\\): missing"):
        select_extractors(registry, ["github", "missing"])
