# Public demo image: scripted answers only, no key, no private photos. Never bake .env into an image.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    BLINDSPOT_PROVIDER=mock BLINDSPOT_HOST=0.0.0.0 BLINDSPOT_PORT=8000
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY blindspot_ci ./blindspot_ci
COPY fixtures ./fixtures
COPY data ./data
COPY datasets ./datasets
RUN pip install -e . && useradd --create-home app && mkdir -p artifacts .blindspot-cache && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('BLINDSPOT_PORT','8000')+'/health',timeout=4)"
CMD ["python", "-m", "blindspot_ci.cli", "serve"]
