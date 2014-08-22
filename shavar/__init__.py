import os

from konfig import Config
from pyramid.config import Configurator
from pyramid.tweens import EXCVIEW

from shavar.lists import configure_lists
from shavar.views import (list_view,
                          downloads_view,
                          gethash_view,
                          newkey_view)

_APP = None


def application(environ, start_response):
    global _APP

    c = Config(os.environ.get('SHAVAR_CFG', 'shavar.ini'))
    if _APP is None:
        _APP = main({}, config_file=c.filename, **c.get_map('shavar'))
    return _APP(environ, start_response)


def main(global_config, config_file=None, _heka_client=None,
         _stats_client=None, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    config = Configurator(settings=settings)

    from shavar.heka_logging import configure_heka
    from shavar.stats import configure_stats

    settings = config.registry.settings

    if _heka_client is None:
        config.registry.heka_client = configure_heka(config_file)
    else:
        config.registry.heka_client = _heka_client

    config.registry.stats_client = configure_stats(
        settings.get('statsd_host'), _client=_stats_client)

    # Set up our data sources
    configure_lists(config_file, settings.get('lists_served', []))

    # timers & counters for response codes
    config.add_tween('shavar.heka_logging.heka_tween_factory', under=EXCVIEW)

    config.add_route('shavar', '/')
    config.add_view(list_view, name='list', route_name='shavar',
                    request_method='GET')
    config.add_view(downloads_view, name='downloads', route_name='shavar',
                    request_method='GET')
    config.add_view(gethash_view, name='gethash', route_name='shavar',
                    request_method='GET')
    config.add_view(newkey_view, name='newkey', route_name='shavar',
                    request_method='GET')

    return config.make_wsgi_app()
