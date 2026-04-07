import os

from pyramid.httpexceptions import HTTPOk


def includeme(config):
    config.add_route("version", "/__version__")
    config.add_view(version_view, route_name="version", request_method=("GET"))


def version_view(request):
    try:
        with open("version.json", "r") as f:
            body = f.read()
    except FileNotFoundError:
        body = "{}"
    return HTTPOk(content_type="text/json", body=body)
