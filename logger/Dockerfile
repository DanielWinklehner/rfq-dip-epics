# The logger (mist2log), its reading tool and its tests. Built by `make -C logger build`.
FROM python:3.12.16-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt /opt/mist2log/requirements.txt
RUN pip install --no-cache-dir -r /opt/mist2log/requirements.txt
COPY mist2log /opt/mist2log/mist2log
ENV PYTHONPATH=/opt/mist2log
USER 1000:1000
WORKDIR /opt/mist2log
ENTRYPOINT []
CMD ["python", "-m", "mist2log"]
