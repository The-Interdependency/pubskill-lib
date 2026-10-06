FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends git nodejs npm && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir . && pip install --no-cache-dir -r .agents/skills/msdmd/requirements.txt
RUN npm ci --ignore-scripts --prefix .agents/skills/msdmd
CMD ["python","service.py"]
