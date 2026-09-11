"""Repository examiner/documenter CLI.

Usage:
    python -m pubskill_lib.examine [--repo PATH] [--apply] [--narrate]
                                   [--out DIR] [--env FILE]

Default is a dry run. Evidence, model reasoning, source mutation,
documentation assembly, and provider access remain separate layers.
"""

from __future__ import annotations

import argparse
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


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _plan(root: Path, evidence_list: list[evidence.FileEvidence]) -> dict:
    supported = [ev for ev in evidence_list if ev.marker is not None]
    return {
        "root": str(root),
        "files": len(evidence_list),
        "supported_files": len(supported),
        "unsupported": [
            {"path": ev.path, "hmmm": ev.hmmm} for ev in evidence_list if ev.marker is None
        ],
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
    now = datetime.now(timezone.utc).isoformat()
    engine = ratios.RatiosEngine()

    for ev in evidence_list:
        path = boundary.assert_inside(root, root / ev.path)
        original_text = _read_text(path)
        adapter = engine.adapter_for(path)
        if ev.marker is None or adapter is None:
            continue

        new_text = original_text
        if narrate:
            result = narrative.narrate_file(
                ev,
                evidence.source_text(original_text, ev.marker),
                provider_list,
                now,
            )
            narratives[ev.path] = result.entry
            if result.hmmm:
                result.entry["summary"] = result.entry["summary"] or "hmmm"
        else:
            existing = ev.narrative_entries[0] if ev.narrative_entries else None
            if existing:
                narratives[ev.path] = existing

        entry = narratives.get(ev.path)
        if entry:
            new_text, block_changed = msdmd_writer.upsert_narrative(
                new_text, ev.marker, entry, path
            )
            if block_changed:
                changed.append(f"{ev.path}:narrative")

        values = engine.compute(path, evidence.source_text(new_text, ev.marker))
        new_text, ratio_changed = engine.place(new_text, ev.marker, values, path)
        if ratio_changed:
            changed.append(f"{ev.path}:ratios")

        if new_text != original_text:
            msdmd_writer.write_text_safely(path, new_text)

    return narratives, {"changed": changed, "narrated": len(narratives)}


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
    out_dir = boundary.assert_inside(root, root / args.out)
    volume = assemble.assemble_docs(root, evidence_list, narratives, out_dir)

    if args.json:
        print(json.dumps({"changed": report["changed"], "volume": str(volume)}, indent=2))
    else:
        print(f"applied: {len(report['changed'])} writes")
        for change in report["changed"]:
            print(f"  {change}")
        print(f"assembled: {volume}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
