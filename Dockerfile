FROM python:2.7
WORKDIR /app
COPY . /app
EXPOSE 6543
ENTRYPOINT pserve shavar.ini
RUN pip install -r requirements.txt --no-cache-dir --disable-pip-version-check \
    && python setup.py install
