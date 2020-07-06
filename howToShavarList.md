##  How To Shavar-List

### Key Ideas

- Shavar implements [SafeBrowsing
  v2](https://web.archive.org/web/20160422212049/https://developers.google.com/safe-browsing/developers_guide_v2#Overview)
  to serve Mozilla-controlled lists of urls.
- Mozilla-controlled lists are sourced in the mozilla-services org on Github.
  E.g., [trackware lists provided by
  Disconnect](https://github.com/mozilla-services/shavar-prod-lists) and
  [plugin
  blocklists](https://github.com/mozilla-services/shavar-plugin-blocklist).
- Every 30m, Jenkins runs our
  [shavar-list-creation/lists2safebrowsing](https://github.com/mozilla-services/shavar-list-creation)
  script to convert the list files on GitHub into SafeBrowsing lists and upload
  them to s3.
- shavar serves lists from s3 as configured in the
  [`shavar-server-list-config`](https://github.com/mozilla-services/shavar-server-list-config)
  repo.

### Adding a new list

Shavar is a small, specific, efficient service for serving lists of urls to
Firefox. We do not plan to enhance its functionality much, except to make the
service easier to maintain and run. So if your project needs something more
than lists of urls, you might look at another service like
[Kinto](https://github.com/Kinto/kinto).

So, if you just need a list of urls ...

1. [File an issue](https://github.com/mozilla-services/shavar/issues/new) in
this repo, including a link back to any relevant bugzilla bug
2. We will ask you to add "upstream" files to an appropriate repository (e.g.,
   shavar-plugin-blocklist, shavar-prod-lists, or a new repo.)
3. We will add the lists to the staging section of our
   [shavar-list-creation](https://github.com/mozilla-services/shavar-list-creation)
   and/or
   [shavar-list-creation-config](https://github.com/mozilla-services/shavar-list-creation-config)
   repositories.
4. When we verify that we're creating and publishing the SafeBrowsing lists to
   S3, we will add the names of the lists to the staging section of
   [shavar-server-list-config](https://github.com/mozilla-services/shavar-server-list-config)
   to make shavar start serving the lists.
5. When we verify that shavar is serving the lists to Firefox correctly, we
   will repeat steps 3-4 for production.

#### QA

When we add new lists to shavar,
[Firefox Test Engineering](https://readthedocs.org/projects/firefox-test-engineering/)
verifies that lists do not disrupt the server-side shavar service. We will
always add the new lists to the staging server first, as described above.

If you need help with client-side testing of Firefox behavior with the new
list, contact the
[SoftVision QA Team](https://wiki.mozilla.org/QA_SoftVision_Team). Typically,
you will need to provide a set of new or updated testing prefs in the
[`services-test/shavar/e2e-test/prefs.ini`](https://github.com/mozilla-services/services-test/blob/master/shavar/e2e-test/prefs.ini)
file.

### Updating list contents

List contents affect all Firefox users, so all list content updates need review
checks. On the shavar side, we check that contents are not going to break nor
block large erroneous parts of the internet for all Firefox users. We will help
you develop those level of review guidelines, but you should perform your own
QA and review to verify that the new list contents work as expected in Firefox.

To update list contents ...

1. Send a pull request to the repository of your "upstream" list files
2. Ideally, the repository contains some automated checks
3. Receive a review and merge from another maintainer of the "upstream" repo
4. Within 30 minutes of the merge, shavar should be serving the new list contents

