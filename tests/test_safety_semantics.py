from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SYSTEM_CORE = ROOT / "system_core"
if str(SYSTEM_CORE) not in sys.path:
    sys.path.insert(0, str(SYSTEM_CORE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import auditor_core  # noqa: E402
import main as cli_main  # noqa: E402
from core.manifest import load_manifest  # noqa: E402
from system_core.services import disk_auditor_service  # noqa: E402


def write_file(path: Path, data: bytes, *, mtime_ns: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if mtime_ns is not None:
        os.utime(path, ns=(mtime_ns, mtime_ns))


@pytest.fixture(autouse=True)
def isolated_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = tmp_path / "project"
    (project / "output").mkdir(parents=True)
    (project / "logs").mkdir()
    (project / "config").mkdir()
    monkeypatch.setattr(auditor_core, "project_root_from_file", lambda: project)
    monkeypatch.setattr(cli_main, "project_root_from_file", lambda: project)
    return project


def test_copy_update_does_not_delete_target_only_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    write_file(source / "new.txt", b"new")
    write_file(target / "extra.txt", b"keep")

    plan = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="copy_update")
    result = auditor_core.apply_plan(plan)

    assert (target / "new.txt").read_bytes() == b"new"
    assert (target / "extra.txt").read_bytes() == b"keep"
    assert result["summary"]["deleted"] == 0
    assert result["summary"]["quarantined"] == 0


def test_mirror_safe_quarantines_target_only_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    write_file(source / "same.txt", b"same")
    write_file(target / "same.txt", b"same")
    write_file(target / "old" / "extra.txt", b"extra")

    plan = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_safe")
    result = auditor_core.apply_plan(plan)

    assert not (target / "old" / "extra.txt").exists()
    quarantined = result["details"]["quarantined"]
    assert quarantined[0]["original_rel_path"] == "old/extra.txt"
    assert quarantined[0]["quarantine_rel_path"].startswith("_audion_quarantine/")
    assert quarantined[0]["quarantine_rel_path"].endswith("old/extra.txt")
    assert result["summary"]["deleted"] == 0
    assert result["summary"]["quarantined"] == 1
    assert result["quarantine_reports"]["json"]
    assert result["quarantine_reports"]["txt"]


def test_mirror_safe_skips_quarantine_after_copy_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    write_file(source / "new.txt", b"new")
    write_file(target / "extra.txt", b"extra")

    def fail_copy(src: Path, dst: Path) -> None:
        raise OSError("copy blocked")

    monkeypatch.setattr(auditor_core, "_safe_copy2", fail_copy)
    plan = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_safe")
    result = auditor_core.apply_plan(plan)

    assert (target / "extra.txt").exists()
    assert result["summary"]["errors"] > 0
    assert result["summary"]["quarantined"] == 0
    assert result["summary"]["phase_skip_reason"] == "Deletion/quarantine phase skipped because earlier phase had errors."


def test_mirror_hard_deletes_target_only_files_without_extra_confirmation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    write_file(target / "extra.txt", b"extra")

    plan = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_hard")
    result = auditor_core.apply_plan(plan)

    assert not (target / "extra.txt").exists()
    assert result["summary"]["errors"] == 0
    assert result["summary"]["deleted"] == 1


def test_mirror_hard_large_delete_ratio_raises_and_override_applies(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    for index in range(auditor_core.DELETE_COUNT_FLOOR + 1):
        write_file(target / f"extra_{index:03}.txt", b"extra")

    plan = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_hard")

    with pytest.raises(auditor_core.DeleteRatioExceeded):
        auditor_core.apply_plan(plan)

    result = auditor_core.apply_plan(plan, override_delete_ratio=True)

    assert result["summary"]["deleted"] == auditor_core.DELETE_COUNT_FLOOR + 1
    assert not any(target.glob("extra_*.txt"))


def test_delete_ratio_guard_ignores_small_targets_below_floor(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    for index in range(auditor_core.DELETE_COUNT_FLOOR - 1):
        write_file(target / f"extra_{index:03}.txt", b"extra")

    plan = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_hard")
    result = auditor_core.apply_plan(plan)

    assert result["summary"]["deleted"] == auditor_core.DELETE_COUNT_FLOOR - 1


def test_mirror_safe_large_ratio_is_not_blocked(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    for index in range(auditor_core.DELETE_COUNT_FLOOR + 1):
        write_file(target / f"extra_{index:03}.txt", b"extra")

    plan = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_safe")
    result = auditor_core.apply_plan(plan)

    assert result["summary"]["quarantined"] == auditor_core.DELETE_COUNT_FLOOR + 1
    assert result["summary"]["deleted"] == 0


def test_mirror_hard_filtered_scope_requires_override(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    write_file(target / "extra.txt", b"extra")
    write_file(target / "extra.bin", b"extra")
    filter_spec = auditor_core.build_filter_spec(include_globs=["*.txt"])

    plan = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_hard", filter_spec=filter_spec)

    with pytest.raises(auditor_core.FilteredHardMirrorBlocked):
        auditor_core.apply_plan(plan)

    result = auditor_core.apply_plan(plan, override_filtered_hard=True)

    assert result["summary"]["deleted"] == 1
    assert not (target / "extra.txt").exists()
    assert (target / "extra.bin").exists()


def test_dry_run_does_not_raise_delete_guards(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    for index in range(auditor_core.DELETE_COUNT_FLOOR + 1):
        write_file(target / f"extra_{index:03}.txt", b"extra")

    plan = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_hard")
    result = auditor_core.apply_plan(plan, dry_run=True)

    assert result["summary"]["would_delete"] == auditor_core.DELETE_COUNT_FLOOR + 1


def test_quarantine_folder_is_excluded_from_future_scans(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    write_file(target / "_audion_quarantine" / "old" / "orphan.txt", b"old")

    plan = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_safe")

    assert plan["items"] == []
    assert plan["summary"]["files_to_quarantine"] == 0


def write_anchor(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / auditor_core.ANCHOR_FILE_NAME).write_text("anchor", encoding="utf-8")


def test_anchor_missing_at_source_raises_source_unreachable(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    write_anchor(target)
    write_file(target / "keep.txt", b"keep")

    with pytest.raises(auditor_core.SourceUnreachable) as excinfo:
        auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_hard", anchor=True)

    assert excinfo.value.role == "source"
    assert "anchor file is missing" in str(excinfo.value)
    assert "disconnected" in str(excinfo.value)


def test_anchor_missing_at_target_raises_source_unreachable(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    write_anchor(source)
    write_file(source / "keep.txt", b"keep")
    target.mkdir()

    with pytest.raises(auditor_core.SourceUnreachable) as excinfo:
        auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_hard", anchor=True)

    assert excinfo.value.role == "target"


def test_anchor_absent_pair_without_flag_still_runs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    write_file(source / "keep.txt", b"keep")
    target.mkdir()

    plan = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_hard")

    assert plan["anchor"] is False
    assert plan["summary"]["files_to_copy"] == 1
    assert plan["preflight"]["anchor"]["status"] == "disabled"
    assert plan["preflight"]["anchor"]["ok"] is True


def test_anchor_file_is_excluded_from_hashes_and_diff(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    write_anchor(source)
    write_anchor(target)
    write_file(source / "a.txt", b"a")

    payload = auditor_core.write_manifest(source)
    entries = auditor_core.parse_manifest(Path(payload["manifest"]))
    plan = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_hard", anchor=True)
    result = auditor_core.apply_plan(plan)

    assert [rel_path for _hash, rel_path in entries] == ["a.txt"]
    assert [item["rel_path"] for item in plan["items"]] == ["a.txt"]
    assert (target / auditor_core.ANCHOR_FILE_NAME).exists()
    assert result["summary"]["deleted"] == 0


def test_mirror_safe_with_anchor_blocks_mass_quarantine(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    write_anchor(target)
    for index in range(auditor_core.DELETE_COUNT_FLOOR + 1):
        write_file(target / f"extra_{index:03}.txt", b"extra")

    with pytest.raises(auditor_core.SourceUnreachable):
        auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_safe", anchor=True)

    assert len(list(target.glob("extra_*.txt"))) == auditor_core.DELETE_COUNT_FLOOR + 1
    assert not (target / auditor_core.QUARANTINE_DIR_NAME).exists()

    write_anchor(source)
    plan = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_safe", anchor=True)

    assert plan["summary"]["files_to_quarantine"] == auditor_core.DELETE_COUNT_FLOOR + 1


def test_apply_refuses_a_confirmation_token_from_a_stale_preview(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    write_file(source / "a.txt", b"a")
    write_file(target / "extra.txt", b"extra")

    preview = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_hard")
    token = preview["preflight"]["confirmation"]["token"]
    write_file(source / "b.txt", b"b")
    fresh = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_hard")

    assert token.startswith("DELETE ")
    with pytest.raises(auditor_core.PreviewConfirmationMismatch):
        auditor_core.apply_plan(fresh, expect_confirmation=token)

    result = auditor_core.apply_plan(fresh, expect_confirmation=fresh["preflight"]["confirmation"]["token"])

    assert result["summary"]["errors"] == 0
    assert (target / "a.txt").exists()


def write_pair_config(path: Path, source: Path, target: Path) -> None:
    payload = {
        "pairs": [
            {
                "name": "copy_by_mask",
                "source": str(source),
                "target": str(target),
                "mode": "safe",
                "sync_kind": "sync",
                "operation_policy": "copy_update",
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_copy_by_mask_fails_without_selected_masks(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    pairs = tmp_path / "pairs.json"
    presets = tmp_path / "presets.json"
    write_pair_config(pairs, source, target)
    presets.write_text('{"presets": {}}', encoding="utf-8")

    code = cli_main.main(["compare", "--pair", "copy_by_mask", "--pairs-config", str(pairs), "--preset-config", str(presets)])

    assert code == 1
    assert "copy_by_mask requires at least one extension mask or extension group" in capsys.readouterr().out


def test_copy_by_mask_copies_only_selected_masks(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    write_file(source / "a.txt", b"text")
    write_file(source / "b.bin", b"bin")
    target.mkdir()
    pairs = tmp_path / "pairs.json"
    presets = tmp_path / "presets.json"
    write_pair_config(pairs, source, target)
    presets.write_text('{"presets": {}}', encoding="utf-8")

    code = cli_main.main(
        [
            "sync",
            "--pair",
            "copy_by_mask",
            "--pairs-config",
            str(pairs),
            "--preset-config",
            str(presets),
            "--mask-globs",
            "*.txt",
        ]
    )

    assert code == 0
    assert (target / "a.txt").read_bytes() == b"text"
    assert not (target / "b.bin").exists()


def test_legacy_dry_run_default_is_ignored_with_warning(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    pairs = tmp_path / "pairs.json"
    presets = tmp_path / "presets.json"
    pairs.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "name": "legacy_backup",
                        "source": str(source),
                        "target": str(target),
                        "mode": "safe",
                        "mirror": True,
                        "dry_run_default": True,
                        "sync_kind": "backup",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    presets.write_text('{"presets": {}}', encoding="utf-8")

    code = cli_main.main(["compare", "--pair", "legacy_backup", "--pairs-config", str(pairs), "--preset-config", str(presets)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["runtime"]["operation_policy"] == "mirror_hard"
    assert auditor_core.DEPRECATED_DRY_RUN_WARNING in payload["runtime"]["warnings"]


def test_quick_and_safe_keep_same_size_same_mtime_as_same(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    stamp = 1_700_000_000_000_000_000
    write_file(source / "same_meta.txt", b"aaaa", mtime_ns=stamp)
    write_file(target / "same_meta.txt", b"bbbb", mtime_ns=stamp)

    quick = auditor_core.compare_dirs(source, target, mode="quick")
    safe = auditor_core.compare_dirs(source, target, mode="safe")

    assert quick["items"][0]["action"] == "same"
    assert quick["items"][0]["reason"] == "size_and_mtime_match"
    assert safe["items"][0]["action"] == "same"
    assert safe["items"][0]["reason"] == "size_and_mtime_match"


def test_strict_detects_same_size_same_mtime_content_difference(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    stamp = 1_700_000_000_000_000_000
    write_file(source / "same_meta.txt", b"aaaa", mtime_ns=stamp)
    write_file(target / "same_meta.txt", b"bbbb", mtime_ns=stamp)

    strict = auditor_core.compare_dirs(source, target, mode="strict")

    assert strict["items"][0]["action"] == "copy"
    assert strict["items"][0]["reason"] == "strict_hash_diff"


def test_sync2_conflict_returns_nonzero_for_real_apply(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    stamp = 1_700_000_000_000_000_000
    write_file(source / "conflict.txt", b"aaaa", mtime_ns=stamp)
    write_file(target / "conflict.txt", b"bbbb", mtime_ns=stamp)

    code = cli_main.main(["sync2", "--source", str(source), "--target", str(target), "--mode", "strict"])

    assert code == 1


def test_filtered_mirror_ignores_out_of_scope_target_files_and_reports_scope(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    write_file(source / "keep.txt", b"keep")
    write_file(target / "extra.bin", b"bin")
    filter_spec = auditor_core.build_filter_spec(include_globs=["*.txt"])

    plan = auditor_core.compare_dirs(source, target, mode="safe", operation_policy="mirror_safe", filter_spec=filter_spec)
    result = auditor_core.apply_plan(plan)

    assert (target / "extra.bin").exists()
    assert result["summary"]["quarantined"] == 0
    assert plan["summary"]["mirror_scope"] == "filtered"
    summary_text = Path(plan["summary_reports"]["txt"]).read_text(encoding="utf-8")
    assert "Filtered mirror: only files matching selected filters are considered" in summary_text


def test_include_dirs_are_case_insensitive(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    write_file(source / "Media" / "Video" / "a.mkv", b"video")
    target.mkdir()
    filter_spec = auditor_core.build_filter_spec(include_dirs=["media"])

    plan = auditor_core.compare_dirs(source, target, mode="safe", filter_spec=filter_spec)

    assert plan["summary"]["files_to_copy"] == 1
    assert plan["items"][0]["rel_path"] == "Media/Video/a.mkv"


def test_custom_manifest_inside_root_is_excluded_from_hashes(tmp_path: Path) -> None:
    root = tmp_path / "root"
    write_file(root / "a.txt", b"a")
    manifest = root / "custom_manifest.b3"
    write_file(manifest, b"stale")

    payload = auditor_core.write_manifest(root, manifest_path=manifest)
    entries = auditor_core.parse_manifest(Path(payload["manifest"]))

    assert [rel_path for _hash, rel_path in entries] == ["a.txt"]


def test_report_output_names_are_unique_for_repeated_runs(isolated_project_root: Path) -> None:
    paths: set[Path] = set()
    for index in range(10):
        path = auditor_core.output_path("rapid")
        auditor_core.save_json(path, {"index": index})
        paths.add(path)

    assert len(paths) == 10


def test_overlapping_source_target_paths_are_blocked(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = source / "target"
    target.mkdir(parents=True)
    write_file(source / "a.txt", b"a")

    with pytest.raises(ValueError, match="overlapping sync"):
        auditor_core.compare_dirs(source, target, mode="safe")


def test_gui_service_passes_quarantine_operation_policy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    captured: dict[str, list[str]] = {}

    class Operation:
        parameters = {
            "cli_command": "backup",
            "source_dir": str(source),
            "target_dir": str(target),
            "mode": "safe",
            "operation_policy": "mirror_safe",
        }

    class Paths:
        pass

    class Context:
        operation = Operation()
        paths = Paths()

        def log(self, message: str) -> None:
            pass

    def fake_run_cli(context: object, args: list[str]) -> dict[str, object]:
        captured["args"] = args
        return {"returncode": 0, "args": args}

    monkeypatch.setattr(disk_auditor_service, "_run_cli", fake_run_cli)
    monkeypatch.setattr(disk_auditor_service, "_record_path_history", lambda *_args, **_kwargs: None)

    result = disk_auditor_service.run_manual_command(Context())

    assert result["returncode"] == 0
    assert captured["args"] == [
        "backup",
        "--source",
        str(source),
        "--target",
        str(target),
        "--mode",
        "safe",
        "--operation-policy",
        "mirror_safe",
    ]


def test_pairs_are_gone_from_the_manifest_for_good() -> None:
    """Профили-пары заменены масками: расширения выбираются группами и
    сохраняются сами, а пара с чужими путями внутри программы больше не нужна.

    Сторожим не форму разделов, а отсутствие возврата: ни узла с `pair_name`,
    ни разделов, которые вокруг них строились. Демонстрационные пары —
    dev_backup, apps_backup, copy_by_mask и прочие — однажды уже стояли рядом с
    настоящими и были неотличимы, пока не откроешь.
    """
    manifest = load_manifest(ROOT / "config" / "tool_manifest.yaml")
    groups = {group.id: group for group in manifest.operation_groups}

    assert "saved_profiles" not in groups, "раздел профилей вернулся"
    assert "preparation" not in groups, "раздел подготовки вернулся"

    def walk(nodes):
        for node in nodes:
            yield node
            yield from walk(node.children)

    with_pairs = [
        node.id
        for node in walk(list(manifest.operation_groups))
        if (node.parameters or {}).get("pair_name")
    ]
    assert not with_pairs, "узлы с pair_name: %s" % ", ".join(with_pairs)

    # Сверка осталась операцией — но своей, в «папка в папку», а не отдельным
    # разделом-обёрткой вокруг одной кнопки.
    folder_to_folder = groups["manual_backup_apply"]
    assert folder_to_folder.service, "сверка и копирование делаются одной командой"


def test_the_safety_switches_reach_the_service_that_understands_them() -> None:
    """A switch is only offered where the command already carries the parameter.
    Showing one that would be quietly ignored is worse than not showing it."""
    import sys

    ROOT_DIR = Path(__file__).resolve().parents[1]
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    from system_core.ui_nicegui.app import (
        SAFETY_SWITCHES,
        apply_safety_switches,
        command_supports_switch,
        root_command_nodes,
        _iter_command_nodes,
        state,
    )

    nodes = {node.id: node for node in _iter_command_nodes(root_command_nodes())}
    mirror = nodes["manual_backup_apply"]

    assert command_supports_switch(mirror, "run_dry")

    state.setdefault("field_values", {})["run_dry"] = True
    try:
        assert apply_safety_switches(mirror, dict(mirror.parameters))["dry_run"] is True
        # An operation whose service knows nothing of it is left alone.
        for node in nodes.values():
            if "dry_run" not in (node.parameters or {}):
                assert "dry_run" not in apply_safety_switches(node, dict(node.parameters))
    finally:
        state["field_values"]["run_dry"] = False

    assert apply_safety_switches(mirror, dict(mirror.parameters))["dry_run"] is False
    assert set(SAFETY_SWITCHES) == {"run_dry", "run_quarantine"}
