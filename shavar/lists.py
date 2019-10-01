import ConfigParser
import StringIO
import logging
import requests
from packaging import version
from urlparse import urlparse

from shavar.exceptions import MissingListDataError, NoDataError
from shavar.sources import (
    DirectorySource,
    FileSource,
    S3DirectorySource,
    S3FileSource
)


logger = logging.getLogger('shavar')
GITHUB_API_URL = 'https://api.github.com'
SHAVAR_PROD_LISTS_BRANCHES_PATH = (
    '/repos/mozilla-services/shavar-prod-lists/branches'
)


def create_list(type_, list_name, settings):
    if type_ == 'digest256':
        list_ = Digest256(list_name, settings['source'], settings)
    elif type_ == 'shavar':
        list_ = Shavar(list_name, settings['source'], settings)
    else:
        raise ValueError('Unknown list type for "%s": "%s"' % (list_name,
                                                               type_))
    return list_


def includeme(config):
    lists_to_serve = config.registry.settings.get('shavar.lists_served', None)
    if not lists_to_serve:
        raise ValueError("lists_served appears to be empty or missing "
                         "in the config \"%s\"!" % config.filename)
    try:
        lists_to_serve_url = urlparse(lists_to_serve)
    except TypeError, e:
        raise ValueError('lists_served must be dir:// or s3+dir:// value')
    lists_to_serve_scheme = lists_to_serve_url.scheme.lower()
    list_configs = []

    config.registry['shavar.serving'] = {}

    if lists_to_serve_scheme == 'dir':
        import os
        list_config_dir = lists_to_serve_url.netloc + lists_to_serve_url.path
        for list_config_file in os.listdir(list_config_dir):
            if list_config_file.endswith(".ini"):
                list_name = list_config_file[:-len(".ini")]
                try:
                    list_config = ConfigParser.ConfigParser()
                    list_config.readfp(open(
                        os.path.join(list_config_dir, list_config_file)
                    ))
                    list_configs.append(
                        {'name': list_name, 'config': list_config}
                    )
                except ConfigParser.NoSectionError, e:
                    logger.error(e)

    elif lists_to_serve_scheme == 's3+dir':
        import boto
        from boto.exception import S3ResponseError

        try:
            conn = boto.connect_s3()
            bucket = conn.get_bucket(lists_to_serve_url.netloc)
        except S3ResponseError, e:
            raise NoDataError("Could not find bucket \"%s\": %s" %
                              (lists_to_serve_url.netloc, e))
        for list_key in bucket.get_all_keys():
            list_key_name = list_key.key
            list_name = list_key_name.rstrip('.ini')
            list_ini = list_key.get_contents_as_string()
            try:
                list_config = ConfigParser.ConfigParser()
                list_config.readfp(StringIO.StringIO(list_ini))
                list_configs.append({'name': list_name, 'config': list_config})
            except ConfigParser.NoSectionError, e:
                logger.error(e)

    else:
        raise ValueError('lists_served must be dir:// or s3+dir:// value')

    for list_config in list_configs:
        list_name = list_config['name']
        list_config = list_config['config']

        # Make sure we have a refresh interval set for the data source for the
        # lists
        setting_name = 'refresh_check_interval'
        settings = dict(list_config.items(list_name))
        default = config.registry.settings.get('shavar.%s' %
                                               setting_name,
                                               10 * 60)
        if setting_name not in settings:
            settings[setting_name] = default

        # defaults = config.get_map('shavar')
        # settings = {'type': 'shavar',
        #            'source': os.path.join(defaults.get('lists_root',
        #                                                ''), lname)}

        type_ = list_config.get(list_name, 'type')
        list_ = create_list(type_, list_name, settings)
        config.registry['shavar.serving'][list_name] = list_

        versioned = (
            list_config.has_option(list_name, 'versioned') and list_config.get(list_name, 'versioned')
        )
        if versioned:
            resp = requests.get(GITHUB_API_URL + SHAVAR_PROD_LISTS_BRANCHES_PATH)
            shavar_prod_lists_branches = resp.json()
            for branch in shavar_prod_lists_branches:
                branch_name = branch.get('name')
                ver = version.parse(branch_name)
                if isinstance(ver, version.Version):
                    # Add version to list config to retrieve later
                    # check if the version exists in S3?
                    # change config to reflect verion branches
                    versioned_source = settings['source'].replace(
                        'tracking/', 'tracking/{}/'.format(branch_name))
                    settings['source'] = versioned_source
                    # get new list for the version
                    list_ = create_list(type_, list_name, settings)
                    versioned_list_name = '{0}-{1}'.format(branch_name, list_name)
                    config.registry['shavar.serving'][versioned_list_name] = list_
                    # revert settings
                    original_source = settings['source'].replace(
                        'tracking/{}/'.format(branch_name), 'tracking/')
                    settings['source'] = original_source
    config.registry.settings['shavar.list_names_served'] = [
        list['name'] for list in list_configs
    ]


def get_list(request, list_name):
    if list_name not in request.registry['shavar.serving']:
        errmsg = 'Not serving requested list "%s"' % (list_name,)
        raise MissingListDataError(errmsg)
    return request.registry['shavar.serving'][list_name]


def lookup_prefixes(request, prefixes):
    """
    prefixes is an iterable of hash prefixes to look up

    Returns a dict of the format:

    { list-name0: { chunk_num0: [ full-hash, ... ],
                    chunk_num1: [ full-hash, ... ],
                    ... },
      list-name1: { chunk_num0: [ full-hash, ... ],
                    ... },
      ... }
    }

    Prefixes that aren't found are ignored
    """

    found = {}

    for list_name, sblist in request.registry['shavar.serving'].iteritems():
        for prefix in prefixes:
            list_o_chunks = sblist.find_prefix(prefix)
            if not list_o_chunks:
                continue
            if list_name not in found:
                found[list_name] = {}
            for chunk in list_o_chunks:
                if chunk.number not in found[list_name]:
                    found[list_name][chunk.number] = []
                found[list_name][chunk.number].extend(chunk.get_hashes(prefix))
    return found


class SafeBrowsingList(object):
    """
    Manages comparisons and data freshness
    """

    # Size of prefixes in bytes
    hash_size = 32
    prefix_size = 4
    type = 'invalid'

    def __init__(self, list_name, source_url, settings):
        self.name = list_name
        self.source_url = source_url
        self.url = urlparse(source_url)
        self.settings = settings

        scheme = self.url.scheme.lower()
        interval = settings.get('refresh_check_interval', 10 * 60)
        if (scheme == 'file' or not (self.url.scheme and self.url.netloc)):
            cls = FileSource
        elif scheme == 's3+file':
            cls = S3FileSource
        elif scheme == 'dir':
            cls = DirectorySource
        elif scheme == 's3+dir':
            cls = S3DirectorySource
        else:
            raise ValueError('Only local single files, local directories, S3 '
                             'single files, and S3 directory sources are '
                             'supported at this time')

        self._source = cls(self.source_url, refresh_interval=interval)
        try:
            self._source.load()
        except NoDataError, e:
            logger.error(e)

    def refresh(self):
        self._source.refresh()

    def delta(self, adds, subs):
        """
        Calculates the delta necessary for a given client to catch up to the
        server's idea of "current"

        This current iteration is very simplistic algorithm
        """
        current_adds, current_subs = self._source.list_chunks()

        # FIXME Should we call issuperset() first to be sure we're not getting
        # weird stuff from the request?
        a_delta = current_adds.difference(adds)
        s_delta = current_subs.difference(subs)
        return sorted(a_delta), sorted(s_delta)

    def fetch(self, add_chunks=[], sub_chunks=[]):
        try:
            details = self._source.fetch(add_chunks, sub_chunks)
        except NoDataError:
            details = {'adds': (), 'subs': ()}
        details['type'] = self.type
        return details

    def fetch_adds(self, add_chunks):
        return self.fetch(add_chunks, [])['adds']

    def fetch_subs(self, sub_chunks):
        return self.fetch([], sub_chunks)['subs']

    def find_prefix(self, prefix):
        # Don't bother looking for prefixes that aren't the right size
        if len(prefix) != self.prefix_size:
            return ()
        return self._source.find_prefix(prefix)


class Digest256(SafeBrowsingList):

    prefix_size = 32
    type = 'digest256'


class Shavar(SafeBrowsingList):

    prefix_size = 4
    type = 'shavar'
