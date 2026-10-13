FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends git nodejs npm && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
# The service resolves the vendored skills from this checkout root, so the
# TypeScript reader runtime installed by npm ci lands in the same tree the
# packaged worker loads from.
ENV PUBSKILL_SKILLS_ROOT=/app/.agents/skills
ARG PUBSKILL_CONSUMER_COMMIT=
ENV PUBSKILL_CONSUMER_COMMIT=$PUBSKILL_CONSUMER_COMMIT
RUN pip install --no-cache-dir . && pip install --no-cache-dir -r .agents/skills/msdmd/requirements.txt
# Fail the image build unless the installed package reports a concrete
# consumer source commit (resolved from a source-owned _build.json, from the
# PUBSKILL_CONSUMER_COMMIT build arg, or from .git). When a source-owned
# identity artifact exists, the installed identity must match it so an
# arbitrary --build-arg cannot override the actual build context.
RUN python - <<'PY'
import json, re, sys
from pathlib import Path
from pubskill_lib.identity import consumer_commit

commit = consumer_commit()
if not re.fullmatch(r"[0-9a-f]{40}", commit):
    sys.exit(f"installed package has no concrete consumer commit: {commit!r}")
source_identity = Path("src/pubskill_lib/_build.json")
if source_identity.is_file():
    recorded = json.loads(source_identity.read_text(encoding="utf-8"))["consumer_commit"]
    if recorded != commit:
        sys.exit(f"installed commit {commit} does not match source identity {recorded}")
print(f"consumer identity verified: {commit}")
PY
RUN npm ci --ignore-scripts --prefix .agents/skills/msdmd
# The committed normalized fixture is the minimal-runtime receipt; the
# deployed image installs the full reader runtime, so it replays the separate
# full-runtime receipt instead.
RUN PYTHONPATH=.agents/skills python -m msdmd.collect \
      --root examples/metadata-repo --repo fixture/metadata-repo \
      --snapshot-identity --strict --json --out /tmp/full-collection.json \
 && python - <<'PY'
import re, sys
from pathlib import Path

def normalized(text: str) -> str:
    return re.sub(r'"version": "Python \d+\.\d+(\.\d+)?"', '"version": "Python <normalized>"', text)

expected = Path("examples/metadata-repo-expected/collection-normalized-full.json").read_text()
actual = normalized(Path("/tmp/full-collection.json").read_text())
if actual != expected:
    sys.exit("full-runtime fixture replay drift")
print("full-runtime fixture replay OK")
PY
CMD ["python","service.py"]
