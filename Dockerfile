FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends git nodejs npm && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
# The service resolves the vendored skills from this checkout root, so the
# TypeScript reader runtime installed by npm ci lands in the same tree the
# packaged worker loads from.
ENV PUBSKILL_SKILLS_ROOT=/app/.agents/skills
RUN pip install --no-cache-dir . && pip install --no-cache-dir -r .agents/skills/msdmd/requirements.txt
RUN npm ci --ignore-scripts --prefix .agents/skills/msdmd
CMD ["python","service.py"]
