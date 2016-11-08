FROM python:2.7
ENV NEWRELIC_LIC_KEY ${NEWRELIC_LIC_KEY:-"1234"}
ENV ENABLE_NEWRELIC $ENABLE_NEWRELIC
RUN useradd -d /app -M -s /bin/sh -u 10001 -U app
WORKDIR /app
ENTRYPOINT ["/app/startup.sh"]
CMD ["START"]
EXPOSE 8080
COPY requirements*.txt /app/
RUN pip install -r requirements.txt --no-cache-dir --disable-pip-version-check && \
      pip install newrelic
COPY . /app
RUN python setup.py install && chown -R app:app /app
