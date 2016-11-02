from shavar import __version__


def includeme(config):
    config.add_route('swagger', '/__api__')
    config.add_view(swagger_view, route_name='swagger',
                    request_method=('GET'),
                    renderer='shavar:templates/swagger.mako')


def swagger_view(request):
    host = request.registry.settings.get('shavar.host')
    if host is None:
        host = request.headers.get('X-Forwarded-Host')
        if host is None:
            host = request.headers.get('Host')

    scheme = request.registry.settings.get('shavar.scheme')
    if scheme is None:
        scheme = request.headers.get('X-Forwarded-Proto')

    request.response.content_type = 'application/x-yaml'
    return {'HOST': host, 'VERSION': __version__,
            'SCHEME': scheme}
