from pyramid.httpexceptions import HTTPOk


VERSION_JSON = ""


with open('version.json', 'r') as f:
    VERSION_JSON = f.read()


def includeme(config):
    config.add_route('version', '/__version__')
    config.add_view(version_view, route_name='version', request_method=('GET'))


def version_view(request):
    return HTTPOk(content_type='text/json', body=VERSION_JSON)
