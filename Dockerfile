FROM python:2.7
RUN useradd -d /app -M -s /bin/sh -u 10001 -U app
WORKDIR /app
ENTRYPOINT ["/app/startup.sh"]
CMD ["START"]
EXPOSE 8080
COPY . /app
RUN pip install -r requirements.txt --no-cache-dir --disable-pip-version-check
RUN python setup.py install && chown -R app:app /app
