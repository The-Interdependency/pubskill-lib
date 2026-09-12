"""Repository examiner/documenter CLI.

Usage:
    python -m pubskill_lib.examine [--repo PATH] [--apply] [--narrate]
                                   [--out DIR] [--env FILE]

Default is a dry run. Evidence, model reasoning, source mutation,
documentation assembly, and provider access remain separate layers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import assemble
from . import boundary
from . import evidence
from . import msdmd_writer
from . import narrative
from . import providers
from . import ratios


def _canonical_artifact(root: Path, path: Path) -> bool:
    candidate = path if path.is_absolute() else root / path
    try:
        return (candidate.relative_to(root).as_posix() == "src/pubskill_lib/_msdmd_universal.py"
                and not candidate.is_symlink()
                and candidate.read_bytes() == Path(evidence._canonical_msdmd.__file__).read_bytes())
    except (OSError, ValueError):
        return False


def _plan(root: Path, evidence_list: list[evidence.FileEvidence]) -> dict:
    engine = ratios.RatiosEngine()
    supported = []
    unsupported = []
    for ev in evidence_list:
        if _canonical_artifact(root, Path(ev.path)):
            continue
        reason = "; ".join(ev.hmmm)
        if ev.marker is None or ev.encoding is None or engine.adapter_for(Path(ev.path)) is None:
            reason = reason or "no safe metrics/write adapter"
        else:
            try:
                path = boundary.assert_inside(root, root / ev.path)
                engine.place(path.read_bytes().decode(ev.encoding), ev.marker, {}, path)
            except (OSError, UnicodeError, ratios.UnsupportedPlacementError) as error:
                reason = str(error)
            else:
                supported.append(ev)
                continue
        unsupported.append({"path": ev.path, "hmmm": [reason]})
    return {
        "root": str(root),
        "files": len(evidence_list),
        "supported_files": len(supported),
        "preserved_authority": [ev.path for ev in evidence_list if _canonical_artifact(root, Path(ev.path))],
        "unsupported": unsupported,
        "ratios_missing": [ev.path for ev in supported if not ev.ratios_lines],
        "narrative_present": [ev.path for ev in supported if ev.narrative_entries],
    }


def _apply(
    root: Path,
    evidence_list: list[evidence.FileEvidence],
    provider_list: list[providers.Provider],
    narrate: bool,
) -> tuple[dict, dict]:
    narratives: dict[str, dict[str, str]] = {}
    changed: list[str] = []
    unresolved: dict[str, str] = {}
    preserved_authority: list[str] = []
    preserved_sources: dict[str, str] = {}
    now = datetime.now(timezone.utc).isoformat()
    engine = ratios.RatiosEngine()

    for ev in evidence_list:
        path = boundary.assert_inside(root, root / ev.path)
        if ev.narrative_entries:
            narratives[ev.path] = ev.narrative_entries[0]
        if _canonical_artifact(root, path):
            preserved_authority.append(ev.path)
            continue
        adapter = engine.adapter_for(path)
        if ev.marker is None or adapter is None or ev.encoding is None:
            unresolved[ev.path] = "; ".join(ev.hmmm) or "no safe metrics/write adapter; mutation skipped"
            continue
        try:
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != ev.raw_sha256:
                unresolved[ev.path] = "source changed after inventory; mutation skipped"
                continue
            original_text = raw.decode(ev.encoding)
        except (OSError, UnicodeError) as exc:
            unresolved[ev.path] = f"source unavailable; mutation skipped: {exc}"
            continue

        try:
            engine.place(original_text, ev.marker, {}, path)
        except ratios.UnsupportedPlacementError as error:
            unresolved[ev.path] = str(error)
            continue
        new_text = original_text
        file_changes: list[str] = []
        entry = narratives.get(ev.path)
        if narrate:
            result = narrative.narrate_file(
                ev,
                evidence.source_text(original_text, ev.marker, path),
                provider_list,
                now,
            )
            entry = result.entry
            if result.hmmm:
                result.entry["summary"] = result.entry["summary"] or "hmmm"
        if entry:
            new_text, block_changed = msdmd_writer.upsert_narrative(
                new_text, ev.marker, entry, path
            )
            if block_changed:
                file_changes.append(f"{ev.path}:narrative")

        values = engine.compute(path, evidence.source_text(new_text, ev.marker, path))
        try:
            new_text, ratio_changed = engine.place(new_text, ev.marker, values, path)
        except ratios.UnsupportedPlacementError as error:
            unresolved[ev.path] = str(error)
            continue
        if ratio_changed:
            file_changes.append(f"{ev.path}:ratios")

        if new_text != original_text:
            try:
                if path.is_symlink() or boundary.assert_inside(root, path) != path or path.read_bytes() != raw:
                    unresolved[ev.path] = "source changed during examination; mutation skipped"
                    continue
                original = msdmd_writer.write_text_safely(path, new_text, ev.encoding, expected_raw=raw)
                preserved_sources[ev.path] = original.relative_to(root).as_posix()
            except msdmd_writer.SourceChangedError as exc:
                unresolved[ev.path] = str(exc)
                continue
            except OSError as exc:
                unresolved[ev.path] = f"source unavailable before write; mutation skipped: {exc}"
                continue
            except UnicodeEncodeError:
                unresolved[ev.path] = f"generated text cannot use {ev.encoding}; mutation skipped"
                continue
        if entry:
            narratives[ev.path] = entry
        changed.extend(file_changes)

    return narratives, {"changed": changed, "narrated": len(narratives), "hmmm": unresolved, "preserved_authority": preserved_authority, "preserved_sources": preserved_sources}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pubskill_lib.examine")
    parser.add_argument("--repo", help="repository path (default: current directory)")
    parser.add_argument("--apply", action="store_true", help="write msdmd + RATIOS + docs")
    parser.add_argument("--narrate", action="store_true", help="call BYOK providers for narratives")
    parser.add_argument("--env", default=".env", help=".env file for BYOK credentials")
    parser.add_argument("--out", default="docs/examiner", help="documentation output directory")
    parser.add_argument("--json", action="store_true", help="emit the plan as JSON")
    args = parser.parse_args(argv)

    try:
        root = boundary.repo_root(args.repo)
        boundary.assert_inside(root, root)
    except (PermissionError, NotADirectoryError) as exc:
        print(f"pubskill_lib.examine: {exc}", file=sys.stderr)
        return 2

    evidence_list = evidence.inventory(root)
    if not args.apply:
        plan = _plan(root, evidence_list)
        if args.json:
            print(json.dumps(plan, indent=2))
        else:
            print(f"dry run: {plan['files']} files, {plan['supported_files']} supported")
            print(f"ratios missing: {len(plan['ratios_missing'])}")
            print(f"narratives present: {len(plan['narrative_present'])}")
            for item in plan["unsupported"][:10]:
                print(f"  hmmm: {item['path']} -> {item['hmmm']}")
        return 0

    env = providers.env_with_dotenv(args.env)
    provider_list = providers.configured_providers(env)
    if args.narrate and not provider_list:
        print("pubskill_lib.examine: --narrate requested but no provider credentials found", file=sys.stderr)
        return 3

    narratives, report = _apply(root, evidence_list, provider_list, args.narrate)
    # Rendering observes live source after every write/skip, so an old summary
    # cannot retain a current marker after a concurrent edit was preserved.
    evidence_list = evidence.inventory(root)
    narratives = {ev.path: ev.narrative_entries[0] for ev in evidence_list if ev.narrative_entries}
    report["narrated"] = len(narratives)
    out_dir = boundary.assert_inside(root, root / args.out)
    volume = assemble.assemble_docs(root, evidence_list, narratives, out_dir)

    if args.json:
        print(json.dumps({**report, "volume": str(volume)}, indent=2))
    else:
        print(f"applied: {len(report['changed'])} writes")
        for change in report["changed"]:
            print(f"  {change}")
        for path, original in report["preserved_sources"].items():
            print(f"  preserved source: {path}: {original}")
        for path, reason in report["hmmm"].items():
            print(f"  hmmm: {path}: {reason}")
        print(f"assembled: {volume}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
