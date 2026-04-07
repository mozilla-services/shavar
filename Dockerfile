# base image, astral-sh's distroless python
FROM ghcr.io/astral-sh/uv:python3.14-trixie

# add the app user
RUN useradd -d /app -M -s /bin/sh -u 10001 -U app
WORKDIR /app

# install project
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# copy src
COPY . .
RUN chown -R app:app /app
USER app

# expose service port
EXPOSE 8000

# set entrypoint and cmd
ENTRYPOINT ["/app/startup.sh"]
CMD ["start"]
