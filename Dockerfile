FROM python:2.7
WORKDIR /app
EXPOSE 8080
ENTRYPOINT uwsgi --ini-paste shavar.ini --paste-logger
COPY . /app
RUN pip install -r requirements.txt --no-cache-dir --disable-pip-version-check \
    && python setup.py install
