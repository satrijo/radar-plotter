FROM condaforge/mambaforge@sha256:050753d138b6708128c9bb45055a9d943f06363f32f63a96f7dd5f304ada52a6

WORKDIR /app
COPY environment.yml /tmp/environment.yml
RUN mamba env create -f /tmp/environment.yml && mamba clean --all --yes
ENV PATH=/opt/conda/envs/pyart_env/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV XDG_CACHE_HOME=/app/cache
ENV MPLCONFIGDIR=/app/cache/matplotlib

COPY . /app
RUN mkdir -p /app/output /app/cache && chown -R 65532:65532 /app
USER 65532:65532

CMD ["python", "worker.py"]
