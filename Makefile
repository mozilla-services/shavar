VIRTUALENV = virtualenv
PYTHON = bin/python
PIP = bin/pip
PIP_CACHE = /tmp/pip-cache.${USER}
BUILD_TMP = /tmp/syncstorage-build.${USER}
PYPI = https://pypi.python.org/simple
INSTALL = $(PIP) install -U -i $(PYPI)
FLAKE8 ?= ./bin/flake8
NOSETESTS ?= ./bin/nosetests
# Not a selective assignment because command line variable assignment means
# make ignores any in-Makefile assignments without the "override" keyword
TAG = Who cares? Testing
REV = $(shell git rev-parse HEAD)
SOURCE = $(shell git config remote.origin.url)
VERSION_JSON = $(shell printf '{"commit":"%s","version":"%s","source":"%s"}' \
		$(REV) "$(TAG)" $(SOURCE))

.PHONY: all build test

all:	build

build:
	$(VIRTUALENV) --no-site-packages --distribute .
	$(INSTALL) Distribute
	$(INSTALL) pip
	$(INSTALL) nose
	$(INSTALL) flake8
	$(INSTALL) -r requirements.txt
	$(PYTHON) ./setup.py develop

test:
	# Check that flake8 passes before bothering to run anything.
	# This can really cut down time wasted by typos etc.
	$(FLAKE8) shavar
	# Generate a version.json just for giggles if one doesn't exist
	@if [ ! -f version.json ]; then \
		echo '{"commit":"1","version":test","source":"testing"}' > version.json; \
	fi;
	# Run the actual testcases.
	$(NOSETESTS) -s ./shavar/tests

tag:
	@if [ "$(TAG)" == 'Who cares? Testing' ]; then \
		echo "Missing TAG= variable on command line."; \
		echo "Usage:\n\tmake tag TAG=0.0.0"; \
		exit 1; \
	fi;
	sed -i -e "s/version=\'.*/version=\'$(TAG)\',/" setup.py
	@echo '$(VERSION_JSON)' > version.json
