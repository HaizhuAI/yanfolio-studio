FROM python:3.12-slim
WORKDIR /srv/yanfolio
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home yanfolio && mkdir -p /data /objects && chown yanfolio /data /objects
COPY app ./app
COPY scripts/create_admin.py scripts/cloud_backup.py ./scripts/
ENV YANFOLIO_DATA=/data
USER yanfolio
EXPOSE 8769
CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8769","--workers","1","--proxy-headers","--forwarded-allow-ips=*"]

