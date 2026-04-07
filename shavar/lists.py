import configparser
import logging
import time
import requests
from packaging import version
from urllib.parse import urlparse

from shavar.exceptions import MissingListDataError, NoDataError
from shavar.sources import DirectorySource, FileSource, S3DirectorySource, S3FileSource


logger = logging.getLogger("shavar")
OLDEST_SUPPORTED_VERSION = "69.0"
VERSION_EMAIL_CATEGORY_INTRODUCED = 97
EMAIL_TRACKER_LISTS = ["base-email-track-digest256", "content-email-track-digest256"]
GITHUB_API_URL = "https://api.github.com"
SHAVAR_PROD_LISTS_BRANCHES_PATH = (
    "/repos/mozilla-services/shavar-prod-lists/branches?per_page=100"
)
BRANCHES_CACHE_TTL = 24 * 60 * 60  # 24 hours

_branches_cache: list | None = None
_branches_cache_time: float = 0.0


def _get_shavar_prod_lists_branches() -> list:
    """Fetch shavar-prod-lists branches from GitHub, with 24h in-process cache.

    Returns an empty list if the request fails, so callers degrade gracefully.
    """
    global _branches_cache, _branches_cache_time
    now = time.monotonic()
    if _branches_cache is not None and (now - _branches_cache_time) < BRANCHES_CACHE_TTL:
        return _branches_cache
    try:
        resp = requests.get(
            GITHUB_API_URL + SHAVAR_PROD_LISTS_BRANCHES_PATH, timeout=10
        )
        resp.raise_for_status()
        _branches_cache = resp.json()
        _branches_cache_time = now
        return _branches_cache
    except Exception as e:
        logger.warning(f"Failed to fetch shavar-prod-lists branches from GitHub: {e}")
        return _branches_cache or []


def create_list(type_, list_name, settings):
    match type_:
        case "digest256":
            return Digest256(list_name, settings["source"], settings)
        case "shavar":
            return Shavar(list_name, settings["source"], settings)
        case _:
            raise ValueError(f'Unknown list type for "{list_name}": "{type_}"')


def get_versioned_list_name(version, list_name):
    return f"{version}-{list_name}"


def get_original_and_versioned_paths(source):
    if "entity/" in source:
        return "entity/", "entity/{}/"
    return "tracking/", "tracking/{}/"


def add_versioned_lists_to_registry(
    settings, serving, ver_lists, type_, list_name, shavar_prod_lists_branches
):
    for branch in shavar_prod_lists_branches:
        try:
            branch_name = branch.get("name")
        except AttributeError as e:
            logger.error(
                "shavar_prod_lists_branches_error",
                extra={
                    "branch": branch,
                    "branches": shavar_prod_lists_branches,
                    "error_message": str(e),
                },
            )
            continue
        ver = version.parse(branch_name)
        if isinstance(ver, version.Version):
            original_path, versioned_path = get_original_and_versioned_paths(
                settings["source"]
            )
            # change config to reflect version branches
            versioned_source = settings["source"].replace(
                original_path, versioned_path.format(branch_name)
            )
            settings["source"] = versioned_source
            # get new list for the version
            list_ = create_list(type_, list_name, settings)
            try:
                list_._source.load()
            except NoDataError:
                logger.info(
                    f"Skipping {ver} version support for {list_name} "
                    "since the file does not exist in S3"
                )
                settings["source"] = settings["source"].replace(
                    versioned_path.format(branch_name), original_path
                )
                continue
            versioned_list_name = get_versioned_list_name(branch_name, list_name)
            serving[versioned_list_name] = list_
            ver_lists[list_name].append(branch_name)
            # revert settings
            settings["source"] = settings["source"].replace(
                versioned_path.format(branch_name), original_path
            )


def includeme(config):
    lists_to_serve = config.registry.settings.get("shavar.lists_served", None)
    if not lists_to_serve:
        raise ValueError(
            f'lists_served appears to be empty or missing in the config "{config.filename}"!'
        )
    try:
        lists_to_serve_url = urlparse(lists_to_serve)
    except TypeError:
        raise ValueError("lists_served must be dir:// or s3+dir:// value")
    lists_to_serve_scheme = lists_to_serve_url.scheme.lower()
    list_configs = []

    serving = {}
    ver_lists = {}

    match lists_to_serve_scheme:
        case "dir":
            import os

            list_config_dir = lists_to_serve_url.netloc + lists_to_serve_url.path
            for list_config_file in os.listdir(list_config_dir):
                if list_config_file.endswith(".ini"):
                    list_name = list_config_file[: -len(".ini")]
                    try:
                        list_config = configparser.ConfigParser()
                        with open(os.path.join(list_config_dir, list_config_file)) as f:
                            list_config.read_file(f)
                        list_configs.append({"name": list_name, "config": list_config})
                    except configparser.NoSectionError as e:
                        logger.error(e)

        case "s3+dir":
            import boto3
            from botocore.exceptions import ClientError

            s3 = boto3.client("s3")
            try:
                s3.head_bucket(Bucket=lists_to_serve_url.netloc)
            except ClientError as e:
                code = e.response["Error"]["Code"]
                if code in ("404", "NoSuchBucket"):
                    raise NoDataError(
                        f'Could not find bucket "{lists_to_serve_url.netloc}": {e}'
                    )
                raise
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=lists_to_serve_url.netloc):
                for obj in page.get("Contents", []):
                    list_key_name = obj["Key"]
                    list_name = list_key_name.rstrip(".ini")
                    response = s3.get_object(
                        Bucket=lists_to_serve_url.netloc, Key=list_key_name
                    )
                    list_ini = response["Body"].read().decode("UTF-8")
                    try:
                        list_config = configparser.ConfigParser()
                        list_config.read_string(list_ini)
                        list_configs.append({"name": list_name, "config": list_config})
                    except configparser.NoSectionError as e:
                        logger.error(e)

        case _:
            raise ValueError("lists_served must be dir:// or s3+dir:// value")

    # Only hit the GitHub API if at least one list requires versioned support
    needs_versioned = any(
        lc["config"].has_option(lc["name"], "versioned")
        and lc["config"].get(lc["name"], "versioned")
        for lc in list_configs
    )
    shavar_prod_lists_branches = _get_shavar_prod_lists_branches() if needs_versioned else []

    for list_config in list_configs:
        list_name = list_config["name"]
        list_config = list_config["config"]

        setting_name = "refresh_check_interval"
        settings = dict(list_config.items(list_name))
        default = config.registry.settings.get(f"shavar.{setting_name}", 10 * 60)
        if setting_name not in settings:
            settings[setting_name] = default

        type_ = list_config.get(list_name, "type")
        list_ = create_list(type_, list_name, settings)
        serving[list_name] = list_
        ver_lists[list_name] = []

        versioned = list_config.has_option(list_name, "versioned") and list_config.get(
            list_name, "versioned"
        )
        if versioned:
            add_versioned_lists_to_registry(
                settings,
                serving,
                ver_lists,
                type_,
                list_name,
                shavar_prod_lists_branches,
            )

    config.registry["shavar.serving"] = serving
    config.registry["shavar.versioned_lists"] = ver_lists
    config.registry.settings["shavar.list_names_served"] = [
        list["name"] for list in list_configs
    ]


def match_with_versioned_list(app_version, supported_versions, list_name):
    try:
        ver = version.parse(app_version)
    except version.InvalidVersion:
        return list_name, None
    # need to be wary of ESR, it's considered legacy version in packaging
    if not isinstance(ver, version.Version) or not supported_versions:
        return list_name, None

    default_ver = version.parse(OLDEST_SUPPORTED_VERSION)
    is_default_version = ver.release and ver.release[0] <= default_ver.release[0]
    if is_default_version:
        return (
            get_versioned_list_name(default_ver.public, list_name),
            default_ver.public,
        )

    if ver.public in supported_versions:
        return get_versioned_list_name(ver.public, list_name), ver.public

    # truncate version to be less specific to lazy match
    truncate_ind = -1
    while len(app_version) != abs(truncate_ind):
        if app_version[:truncate_ind] in supported_versions:
            versioned_list_name = get_versioned_list_name(
                app_version[:truncate_ind], list_name
            )
            return versioned_list_name, app_version[:truncate_ind]
        truncate_ind -= 1

    # get the major version and match to that
    major_ver = str(float(ver.release[0]))
    if major_ver in supported_versions:
        return get_versioned_list_name(major_ver, list_name), major_ver

    # if none of the supported versions match, match with master
    return list_name, None


def get_list(request, list_name, app_ver="none"):
    shavar_lists_served = request.registry["shavar.serving"]
    if list_name not in shavar_lists_served:
        raise MissingListDataError(f'Not serving requested list "{list_name}"')
    all_supported_versions = request.registry["shavar.versioned_lists"]
    list_name, list_ver = match_with_versioned_list(
        app_ver, all_supported_versions.get(list_name), list_name
    )
    registry_val = request.registry["shavar.serving"].get(list_name)
    return registry_val, list_ver


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

    for list_name, sblist in request.registry["shavar.serving"].items():
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
    type = "invalid"

    def __init__(self, list_name, source_url, settings):
        self.name = list_name
        self.source_url = source_url
        self.url = urlparse(source_url)
        self.settings = settings

        scheme = self.url.scheme.lower()
        interval = settings.get("refresh_check_interval", 10 * 60)

        if not (self.url.scheme and self.url.netloc):
            # Relative or plain path — treat as local file
            cls = FileSource
        else:
            match scheme:
                case "file":
                    cls = FileSource
                case "s3+file":
                    cls = S3FileSource
                case "dir":
                    cls = DirectorySource
                case "s3+dir":
                    cls = S3DirectorySource
                case _:
                    raise ValueError(
                        "Only local single files, local directories, S3 "
                        "single files, and S3 directory sources are "
                        "supported at this time"
                    )

        self._source = cls(self.source_url, refresh_interval=interval)
        try:
            self._source.load()
        except NoDataError as e:
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

    def fetch(self, add_chunks=None, sub_chunks=None):
        if add_chunks is None:
            add_chunks = []
        if sub_chunks is None:
            sub_chunks = []
        try:
            details = self._source.fetch(add_chunks, sub_chunks)
        except NoDataError:
            details = {"adds": (), "subs": ()}
        details["type"] = self.type
        return details

    def fetch_adds(self, add_chunks):
        return self.fetch(add_chunks, [])["adds"]

    def fetch_subs(self, sub_chunks):
        return self.fetch([], sub_chunks)["subs"]

    def find_prefix(self, prefix):
        # Don't bother looking for prefixes that aren't the right size
        if len(prefix) != self.prefix_size:
            return ()
        return self._source.find_prefix(prefix)


class Digest256(SafeBrowsingList):
    prefix_size = 32
    type = "digest256"


class Shavar(SafeBrowsingList):
    prefix_size = 4
    type = "shavar"
