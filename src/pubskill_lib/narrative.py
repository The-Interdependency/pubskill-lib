"""Model reasoning layer: evidence-bound narrative generation.

A narrative is descriptive evidence about one file, bound to the exact content
hash that produced it. Successful generations also record provider and model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import evidence
from . import providers
from .msdmd_writer import narrative_id

SYSTEM_PROMPT = (
    "You are a repository examiner. Describe exactly what the given source file "
    "does, based only on the code shown. Do not infer behavior from file names, "
    "directories, or conventions. Do not invent contracts, capabilities, or "
    "security claims. Be concrete and cite the actual functions, classes, and "
    "data flow you can see. If the file is empty or unreadable, say so. "
    "Answer in 3-6 sentences of plain prose. Do not use markdown headings."
)


@dataclass
class Narrative:
    path: str
    entry: dict[str, str]
    hmmm: list[str] = field(default_factory=list)


def _user_prompt(ev: evidence.FileEvidence, text: str) -> str:
    return (
        f"File path: {ev.path}\n"
        f"Language: {ev.language}\n"
        f"Shebang: {ev.shebang or 'none'}\n"
        f"Existing msdmd blocks: {', '.join(sorted(ev.msdmd_blocks)) or 'none'}\n\n"
        f"Code:\n{text}"
    )


def narrate_file(
    ev: evidence.FileEvidence,
    text: str,
    provider_list: list[providers.Provider],
    now: str,
) -> Narrative:
    entry = {
        "id": narrative_id(ev.sha256),
        "summary": "",
        "evidence_sha256": ev.sha256,
        "model": "hmmm",
        "provider": "hmmm",
        "generated_at": now,
        "stale": "false",
    }
    hmmm: list[str] = []

    if ev.marker is None:
        hmmm.append(f"unsupported language for narrative block: .{ev.language}")
    elif not provider_list:
        hmmm.append("no BYOK provider credentials configured")
    elif not text.strip():
        entry["summary"] = "The file is empty."
        entry["model"] = "none"
        entry["provider"] = "none"
    else:
        try:
            summary, name, model = providers.chat_with_fallback(
                provider_list, SYSTEM_PROMPT, _user_prompt(ev, text)
            )
            entry["summary"] = " ".join(summary.split())
            entry["provider"] = name
            entry["model"] = model or "hmmm"
        except Exception as exc:  # provider failure remains visible as hmmm
            hmmm.append(f"model reasoning failed: {type(exc).__name__}")

    if hmmm:
        entry["summary"] = entry["summary"] or "hmmm: " + "; ".join(hmmm)
        entry["model"] = "hmmm"
    return Narrative(path=ev.path, entry=entry, hmmm=hmmm)


def is_stale(entry: dict[str, str], current_sha256: str) -> bool:
    return entry.get("evidence_sha256") != current_sha256
