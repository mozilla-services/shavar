shavar - a service that speaks Google's safe browsing protocol

For more information on safe browsing and the wire protocol this code
speaks, see:

  https://developers.google.com/safe-browsing/developers_guide


Running locally with Docker
---------------------------

Generate a `version.json` file::

    echo '{"commit":"1","version":test","source":"testing"}' > version.json

Build the docker image::

    docker build .

Run the image in a container with port 8080 published to the host::

    docker run -p 8080:8080 <image>

Check that it's working::

    curl -v -d" " localhost:8080/list

Run tests
---------

1. Install test dependencies (probably into a virtualenv)::

    pip install -r requirements-test.txt

2. Tests use boto; so make sure your ~/.boto config works

3. Run the tests with `nosetests`::

    nosetests -s ./shavar/tests


Configuration
-------------

The shavar service serves changes to a set of hashes of canonicalized URLs.
Basic configuration consists of specifying the names of the lists to be served
and a section for each of those lists declaring at least the two minimum
required configuration directives for each list.

A commented example configuration::

    [shavar]
    # A newline separated list of the lists to be served.  The names given
    # here will be used to locate the list specific configuration stanzas
    # elsewhere in the INI file.
    lists_served = mozpub-track-digest256
                   moz-abp-shavar
                   moz-bananas-shavar
    # The default protocol version to speak.  As yet, we only speak version
    # 2 of the protocol even though it has been superceded by Google.
    # Default value: 2
    default_proto_ver = 2.0
    # The root directory for the data files for lists if absolute path names
    # are not provided in the list specific stanzas.  Not necessary if you
    # provide absolute paths.
    lists_root = tests

    # This is the public host and scheme to reach the service
    # like https://shavar.stage.mozaws.net
    # when not provided, uses X-Forwarded-Host then fallsback to HTTP_HOST
    # and X-Forwarded-Proto for the scheme
    host = shavar.in.production.mozilla.com
    scheme = https

    [mozpub-track-digest256]
    # The type of list data that will be shipped.  Presumably this has some
    # greater impact on the client side but as yet, it isn't used for much
    # other than making sure the list's name and type match.
    #
    # The technical difference between the shavar and digest256 list types
    # is that digest256 formatted lists use the entire 32 byte SHA256 hash
    # in the list data while shavar formatted list only send the first 4
    # bytes of the 32 byte hash.  The client then queries the service if it
    # encounters a match for a given hash prefix(the first 4 bytes) to
    # retrieve the entire hash for a given prefix.
    type = digest256
    # URL or relative path to the source data for this list.  Possibilities
    # at the moment include:
    #
    # relative/path/to/the/file
    # /absolute/path/to/the/file
    # file:///absolute/path/to/the/file
    # s3+file:///s3_bucket_name/s3_key_name_which_can_include_slashes
    #
    # In this usage, "my_s3_bukkit" is the S3 bucket name and
    # "faux/path/to/file/moz-abp-shavar.data" is the full key name.  This
    # just permits slight simulation of a file name.
    source = s3+file:///my_s3_bukkit/faux/path/to/file/mozpub-track-digest256.data

    [moz-abp-shavar]
    # Firefox currently (as of 2015-07-13) allows digest256 lists to get away
    # with breaking the safe browsing wire protocol slightly.  The protocol
    # actually states that the service's response to a client request for
    # updated data be formatted as a list of URLs to data files to be
    # downloaded.
    #
    # With Firefox, digest256 changes can be served inline in the initial
    # response.  Naughty Firefox.  No cookie.
    #
    type = shavar
    # delta_chunk_source is part of the unit test suite and should always be
    # available to test against.
    source = shavar/tests/delta_chunk_source
    # As a result of this use of URLs(referred to as redirects in the protocol
    # specification document given at the top of the README), it is necessary
    # for the service to know where the data files will be publicly reachable.
    # This setting provides the base URL that, when combined with the path
    # portion of the URL given in the `source` directive above, will be the
    # redirect served in the response.
    #
    # Best practice: make sure it ends in a /
    redirect_url_base = http://localhost:6543/data/

