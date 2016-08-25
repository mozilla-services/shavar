FROM python:2.7
RUN groupadd -g 10001 app && useradd -d /app -g 10001 -G app -M -s /bin/sh -u 10001 app
WORKDIR /app
ENTRYPOINT ["/app/startup.sh"]
CMD ["START"]
EXPOSE 8080
COPY . /app
RUN pip install -r requirements.txt --no-cache-dir --disable-pip-version-check \
    && python setup.py install && chown -R app:app /app
