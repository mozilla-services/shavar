FROM python:2.7
WORKDIR /app
EXPOSE 6543
ENTRYPOINT pserve shavar.ini
COPY . /app
RUN pip install -r requirements.txt --no-cache-dir --disable-pip-version-check \
    && python setup.py install
