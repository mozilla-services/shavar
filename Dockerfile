FROM python:2.7
WORKDIR /app
EXPOSE 8080
RUN groupadd -g 10001 app && useradd -d /app -g 10001 -G app -M  -s /bin/sh -u 10001 app
ENTRYPOINT uwsgi --ini-paste shavar.ini --paste-logger --uid 10001 --gid 10001
COPY . /app
RUN pip install -r requirements.txt --no-cache-dir --disable-pip-version-check \
    && python setup.py install && chown -R app:app /app
