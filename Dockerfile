FROM python:3.10-bookworm
WORKDIR /app
COPY . .
RUN    pip install --no-cache-dir -r ./PyLoggingBackend/requirements.txt \
    && pip install --no-cache-dir -r ./MyPythonUtility/requirements.txt \
    && pip install --no-cache-dir -r requirements.txt \
    && pip cache purge \
    && playwright install-deps \
    && playwright install chromium
# CMD sh -c "python IntelligenceHubLauncher.py & python ServiceEngine.py & wait"