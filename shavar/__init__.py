from konfig import Config
from pyramid.config import Configurator
from pyramid.tweens import EXCVIEW

from shavar.heka_logging import configure_heka
from shavar.lists import configure_lists
from shavar.stats import configure_stats

from shavar.views import (list_view,
                          downloads_view,
                          gethash_view,
                          newkey_view)


def read_config(config_file, settings):
    config = Config(config_file)

    for key, value in config.get_map('shavar').iteritems():
        settings['shavar.%s' % key] = value

    # Also populate the individual list sections
    for list_name in config.mget('shavar', 'lists_served'):
        for key, value in config.get_map(list_name).iteritems():
            settings['%s.%s' % (list_name, key)] = value


def main(global_config, _heka_client=None, _stats_client=None, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    read_config(global_config['__file__'], settings)

    config = Configurator(settings=settings)

    settings = config.registry.settings

    if _heka_client is None:
        config.registry.heka_client = configure_heka(global_config['__file__'])
    else:
        config.registry.heka_client = _heka_client

    config.registry.stats_client = configure_stats(settings['shavar.statsd_host'],
                                                   _client=_stats_client)

    # Set up our data sources
    configure_lists(global_config['__file__'], config.registry)

    # timers & counters for response codes
    config.add_tween('shavar.heka_logging.heka_tween_factory', under=EXCVIEW)

    config.add_route('list', '/list')
    config.add_view(list_view, route_name='list', request_method='GET')

    config.add_route('downloads', '/downloads')
    config.add_view(downloads_view, route_name='downloads',
                    request_method='POST')

    config.add_route('gethash', '/gethash')
    config.add_view(gethash_view, route_name='gethash', request_method='POST')

    config.add_route('newkey', '/newkey')
    config.add_view(newkey_view, route_name='newkey', request_method='GET')

    return config.make_wsgi_app()
