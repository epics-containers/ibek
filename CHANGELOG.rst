Changelog
=========

Unreleased
----------

Added
~~~~~

Templates can read the ibek process environment with ``{{ env.NAME }}``,
``{{ env['NAME'] }}``, or ``{{ env.get('NAME', 'fallback') }}``.
The mapping is read-only and reflects the environment at render time.

Direct access to a missing variable fails in entity expressions; use ``get``
when a fallback is intentional. An empty but defined variable remains empty.
The final assembly templates retain their existing permissive handling of
missing values. Existing entity fields and shared variables named ``env``
take precedence over the new helper.

``_global`` remains supported, with no deprecation or migration requirement.
In particular, ``_global.get_env('NAME')`` still returns an empty string for an
unset variable. Older ibek releases without the new ``env`` mapping should
continue to use that form.

Fixed
~~~~~

``ibek pattern schema`` failed with ``CERTIFICATE_VERIFY_FAILED`` on RHEL when
run through ``uvx``, because the uv-managed Python looks for CA certificates
at ``/etc/ssl/cert.pem``. Schema downloads now verify against the operating
system trust store with ``truststore`` (#364).

The published schema cache no longer assumes release tags are immutable.
Each run revalidates the cached copy with ``If-None-Match`` /
``If-Modified-Since``, and uses the cached copy when a fetch fails.

A failed fetch no longer leaves a possibly stale ``ioc.schema.json`` in place
silently. If nothing is cached for the image tag and the instance already has
a schema, ``ibek pattern schema`` exits 1. Only a 404 or 410 response still
skips generation quietly.

Documentation
~~~~~~~~~~~~~

Replaced the maintained guides and references with compact documentation of
the CLI lifecycle, YAML and Jinja rendering, ibek-support Ansible recipes,
and ibek's role in epics-containers. Added runnable rendering tutorials and
documented the persistent schema cache used by ``ibek pattern`` (issue #365).

Published releases are listed on
`GitHub <https://github.com/epics-containers/ibek/releases>`_.
