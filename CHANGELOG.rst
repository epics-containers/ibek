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

Documentation
~~~~~~~~~~~~~

Replaced the maintained guides and references with compact documentation of
the CLI lifecycle, YAML and Jinja rendering, ibek-support Ansible recipes,
and ibek's role in epics-containers. Added runnable rendering tutorials and
documented the persistent schema cache used by ``ibek pattern`` (issue #365).

Published releases are listed on
`GitHub <https://github.com/epics-containers/ibek/releases>`_.
