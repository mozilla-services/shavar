from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound, HTTPOk
from shavar.utils import parse_downloads, parse_gethash, setting


# Protocol version 2
# See https://developers.google.com/safe-browsing/developers_guide_v2

def list_view(request):
    lists = setting(request, 'lists_served', ('nada'))
    result = HTTPOk()
    result.content_type = 'text/plain'
    # *NOT* semicolon terminated
    result.body = '\n'.join(lists)
    return result


def downloads_view(request):
    proto_ver = request.GET.get('pver', setting(request, 'default_proto_ver',
                                                '1.0'))

    return HTTPNotFound()


def gethash_view(request):
    return HTTPNotFound()


def newkey_view(request):
    return HTTPNotFound()

