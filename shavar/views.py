from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPNotFound,
    HTTPNotImplemented,
    HTTPServiceUnavailable,
    HTTPOk)

from shavar.exceptions import NoDataError
from shavar.heka_logging import get_heka_client
from shavar.lists import get_list, lookup_prefixes
from shavar.parse import parse_downloads, parse_gethash
from shavar.stats import get_stats_client


def _setting(request, key, default):
    return request.registry.settings.get(key, default)


def list_view(request):
    lists = request.registry.settings.get('lists_served', tuple())
    result = HTTPOk()
    result.content_type = 'text/plain'
    # *NOT* semicolon terminated
    result.body = '\n'.join(lists)
    return result


def downloads_view(request):
    heka_client = get_heka_client()
    stats_client = get_stats_client()

    resp_payload = {'interval': _setting(request, 'default_interval', 45 * 60),
                    'lists': {}}

    parsed = parse_downloads(request)

    for lname, wants_mac, claims in parsed['lists']:
        # Do we even serve that list?
        if lname not in _setting(request, 'lists_served', tuple()):
            heka_client.warn('Unknown list "%s" reported; ignoring' % lname)
            stats_client.incr('downloads.unknown.list')
            continue
        provider, type_, format_ = lname.split('-', 3)
        if not provider or not type_ or not format_:
            heka_client.warn('Unknown list format for "%s"; ignoring' % lname)
            stats_client.incr('downloads.unknown.format')
            raise HTTPBadRequest('Incorrect format for the list name: "%s"'
                                 % lname)

        # A list in digest256 format means ignore the normal response body
        # format of shavar and send a blob of the full length hashes directly
        if format_ == "digest256":
            try:
                resp_payload['lists'][lname] = get_list(lname).fetch()
            except NoDataError:
                # We can't find the data for that list
                heka_client.raven('Error reading digest256 list: %s' % lname)
                stats_client.incr('downloads.list.%s.missing' % lname)
                # Continue because protocol says ignore errors with lists
        elif format_ == "shavar":
            sblist = get_list(lname)

            # Calculate delta
            to_add, to_sub = sblist.delta(claims)

            # No delta?  No response, I think.  Spec doesn't actually say.
            if not to_add and not to_sub:
                continue

            # Fetch the appropriate chunks
            resp_payload['lists'][lname] = sblist.fetch(to_add, to_sub)

    # Format response body according to protocol version
    proto_ver = float(request.GET.get('pver', _setting(request,
                                                       'default_proto_ver',
                                                       '2.0')))
    if proto_ver >= 2.0 and proto_ver < 3.0:
        payload = format_v2_downloads(request, resp_payload)
        stats_client.incr('downloads.format.v2')
    elif proto_ver >= 3.0:
        payload = format_v3_downloads(request, resp_payload)
        stats_client.incr('downloads.format.v3')

    return HTTPOk(payload)


def gethash_view(request):
    heka_client = get_heka_client()
    stats_client = get_stats_client()

    parsed = parse_gethash(request)

    return HTTPNotFound()


def newkey_view(request):
    heka_client = get_heka_client()
    stats_client = get_stats_client()

    return HTTPNotImplemented()


def format_v2_downloads(request, payload):
    body = "n:" + payload['interval'] + "\n"

    for lname, ldata in payload['lists'].items():
        # digest256 lists don't use URL redirects for data.  They simply include
        # the data inline in the response
        if ldata['type'] == 'digest256':
            body += ""
        elif ldata['type'] == 'shavar':
            body += ""

    return body


def format_v2_gethash(request, payload):
    pass


def format_v3_downloads(request, payload):
    pass
