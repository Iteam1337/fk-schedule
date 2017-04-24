FROM python:3.6

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app
ENV FLASK_APP app.py
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY manage.py .
COPY app.py .

EXPOSE 5000
CMD sleep 10 && python manage.py initdb && flask run --host 0.0.0.0
