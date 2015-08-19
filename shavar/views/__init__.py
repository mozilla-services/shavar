from itertools import chain
import logging
import os

from mozsvc.metrics import annotate_request

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPNoContent,
    HTTPNotImplemented,
    HTTPOk,
    HTTPInternalServerError)

from shavar.exceptions import ParseError
from shavar.lists import get_list, lookup_prefixes
from shavar.parse import parse_downloads, parse_gethash


logger = logging.getLogger('shavar')


def includeme(config):
    config.add_route('list', '/list')
    config.add_view(list_view, route_name='list', request_method=('GET',
                                                                  'POST'))

    config.add_route('downloads', '/downloads')
    config.add_view(downloads_view, route_name='downloads',
                    request_method='POST')

    config.add_route('gethash', '/gethash')
    config.add_view(gethash_view, route_name='gethash', request_method='POST')

    config.add_route('newkey', '/newkey')
    config.add_view(newkey_view, route_name='newkey', request_method='GET')


def _setting(request, section, key, default=None):
    return request.registry.settings.get("%s.%s" % (section, key), default)


def list_view(request):
    lists = _setting(request, 'shavar', 'lists_served', tuple())

    body = '\n'.join(lists) + '\n'
    return HTTPOk(content_type='text/plain', body=body)


def downloads_view(request):
    resp_payload = {'interval': _setting(request, 'shavar', 'default_interval',
                                         45 * 60),
                    'lists': {}}

    parsed = parse_downloads(request)

    for list_info in parsed:
        # Do we even serve that list?
        if list_info.name not in _setting(request, 'shavar', 'lists_served',
                                          tuple()):
            logger.warn('Unknown list "%s" reported; ignoring'
                        % list_info.name)
            annotate_request(request, "shavar.downloads.unknown.list", 1)
            continue
        provider, type_, format_ = list_info.name.split('-', 3)
        if not provider or not type_ or not format_:
            s = 'Unknown list format for "%s"; ignoring' % list_info.name
            logger.error(s)
            annotate_request(request, "shavar.downloads.unknown.format", 1)
            raise HTTPBadRequest(s)

        sblist = get_list(request, list_info.name)

        # Calculate delta
        to_add, to_sub = sblist.delta(list_info.adds, list_info.subs)

        # No delta?  No response, I think.  Spec doesn't actually say.
        if not to_add and not to_sub:
            continue

        # Fetch the appropriate chunks
        resp_payload['lists'][list_info.name] = sblist.fetch(to_add, to_sub)

        # Not publishing deltas for this list?  Delete all previous chunks to
        # make way for the new corpus
        if _setting(request, list_info.name, 'not_publishing_deltas'):
            # Raise hell if we have suspicious data with this flag set
            if (len(to_add) != 1 or len(to_sub) != 0):
                logger.error("Configuration error!  Mismatch between "
                             "{0}'s configuration has "
                             "'not_publishing_deltas' enabled but its data"
                             "file has more than one chunk to serve."
                             .format(list_info.name))
                raise HTTPInternalServerError()
            resp_payload['lists'][list_info.name]['adddels'] = list_info.adds

    return HTTPOk(content_type="application/octet-stream",
                  body=format_downloads(request, resp_payload))


def format_downloads(request, resp_payload):
    """
    Formats the response body according to protocol version
    """
    body = "n:{0}\n".format(resp_payload['interval'])

    for lname, ldata in resp_payload['lists'].iteritems():
        body += "i:%s\n" % lname

        # Chunk deletion commands come first
        if 'adddels' in ldata and ldata['adddels']:
            dels = ','.join(['{0}'.format(num) for num in ldata['adddels']])
            body += 'ad:{0}\n'.format(dels)
        if 'subdels' in ldata and ldata['subdels']:
            dels = ','.join(['{0}'.format(num) for num in ldata['subdels']])
            body += 'sd:{0}\n'.format(dels)

        # TODO  Should we prioritize subs over adds?
        for chunk in chain(ldata['adds'], ldata['subs']):
            # digest256 lists don't use URL redirects for data.  They simply
            # include the data inline in the response
            if ldata['type'] == 'digest256':
                d = ''.join(chunk.hashes)
                data = "{type}:{chunk_num}:{hash_len}:{payload_len}\n" \
                       "{payload}".format(type=chunk.type,
                                          chunk_num=chunk.number,
                                          hash_len=chunk.hash_len,
                                          payload_len=len(d), payload=d)
            elif ldata['type'] == 'shavar':
                fudge = os.path.join(_setting(request, lname,
                                              'redirect_url_base'),
                                     lname, "%d" % chunk.number)
                data = 'u:{0}\n'.format(fudge)
            else:
                s = 'unsupported list type "%s" for "%s"' % (lname,
                                                             ldata['type'])
                logger.error(s)
            body += data
    return body


#
# gethash
#
def gethash_view(request):
    try:
        parsed = parse_gethash(request)
    except ParseError, e:
        annotate_request(request, "shavar.gethash.unknown.format", 1)
        raise HTTPBadRequest(str(e))

    full = lookup_prefixes(request, parsed)

    # Nothing found?  Return a 204
    if len(full) == 0:
        return HTTPNoContent()

    # FIXME MAC handling
    body = ''
    for lname, chunk_data in full.items():
        for chunk_num, hashes in chunk_data.iteritems():
            h = ''.join(hashes)
            body += '{list_name}:{chunk_number}:{data_len}\n{data}' \
                .format(list_name=lname, chunk_number=chunk_num,
                        data_len=len(h), data=h)

    return HTTPOk(content_type="application/octet-stream", body=body)


def newkey_view(request):
    # Not implemented at the moment because Mozilla requires HTTPS for its
    # hosting site.  As a result the implmementation has been delayed a bit.
    return HTTPNotImplemented()
