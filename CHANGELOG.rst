Changelog
=========

Unreleased
----------

Added
~~~~~

``ibek dev`` commands for a devcontainer that runs a pre-built generic IOC
image, where the host project mounted over ``/epics/generic-source`` can
differ from the tree the image was built from. ``ibek dev stamp``, run as the
last step of the Dockerfile's developer stage, records that tree in
``/epics/dev-stamp.json``. ``ibek dev status`` shows how the mounted project
differs. ``ibek dev sync`` links changed support definition files, removes
dangling links and regenerates the IOC schema, and reports what needs a
build; ``ibek dev sync --build`` also rebuilds the out of date support
modules, those after them in the Dockerfile, and the IOC, cloning a module
again only when its ``install.yml`` asks for a different source. ``ibek dev
instance`` prints the same report. In an image with no stamp each command
says so and exits 0. See ``docs/reference/cli.md``.

``ibek dev status``, ``ibek dev sync`` and ``ibek dev instance`` start their
report with a ``WARNING:`` line when the container was created from a different
developer image than the one now on the host: when
``/epics/dev-image-id``, written as the container is created, differs from
``/epics/generic-source/.devcontainer/image-id``, written by the host as the
devcontainer starts. With either file missing or empty nothing is said, and
no exit code changes.

``ibek pattern install library:pattern@version ...`` installs runtime patterns
into a generic IOC image at build time, beside its compiled support modules:
support YAML to ``/epics/ibek-defs``, PVI device YAML to ``/epics/pvi-defs``,
protocols to ``/epics/support/configure/protocol``, and templates, databases
and req files to ``/epics/support/<library>/db``. Every destination is planned
first, and a run that would collide with the image or with itself writes
nothing. Installed patterns are recorded, with each file's SHA-256 and the
library commit, in ``/epics/ibek-defs/runtime-patterns.lock.yaml``, which
``ibek pattern check --image`` verifies. ``ibek runtime generate2`` warns when
an instance's ``config/`` defines a module the image also defines.
See `#395 <https://github.com/epics-containers/ibek/issues/395>`_.

``ibek pattern schema`` finds the base schema of an image published on GitLab.
For an image on a GitLab host listed in ``IBEK_GITLAB_HOSTS`` (``host[:port]``
entries) or the CI job's server, ibek reads the ``ibek.ioc.schema.json`` link
of release ``<tag>`` through
``https://<web host>/api/v4/projects/<project path>/releases/<tag>/assets/links``,
where the web host is the registry host without its port or ``registry.``
prefix and the project path is the image path without its last part, then
downloads that link. An image on any other registry that is not GitHub or
Docker Hub is skipped. At DLS set ``IBEK_GITLAB_HOSTS=gitlab.diamond.ac.uk``.
ibek sends ``GITLAB_TOKEN`` as ``PRIVATE-TOKEN`` only over HTTPS to a listed
host and port, never to GitHub, and never after a redirect to another origin,
even one that redirects back; the token is scoped to the listed origin, not to
one project, and as defence in depth a release asset gets it only at a package
or project web path on that origin; without it, GitLab CI's
``CI_JOB_TOKEN`` is sent as ``JOB-TOKEN`` to the job's own server only. An
instance can record its schema URL in ``runtime-lock.yaml`` with
``ibek pattern schema --schema-url URL``, which records it only after a schema
is generated from it, and ``IBEK_SCHEMA_URL`` overrides it for one run; both
must be ``https://`` URLs and accept ``{registry}``, ``{project}``,
``{project_encoded}``, ``{name}`` and ``{tag}``. ibek fetches schemas only over
HTTPS, and refuses a fetched schema without the shape of an ibek IOC schema. A
lock with a ``schema_url`` is written as ``version: 3``. See
``docs/reference/paths-and-environment.md`` (#375).

Entity models accept a ``validate`` list of checks, each with an ``assert``
Jinja expression (written without ``{{ }}``) and a ``message`` that may contain
Jinja. The checks run against each enabled instance after its
``pre_defines``, parameters and ``post_defines`` are rendered, so they can read
fields of object parameters, for example
``assert: interrupt_vector.count == 3``. A false assertion stops generation
with ``<module>.<name>: validation failed: <message>`` (#64).

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

``ibek pattern add`` takes ``--include SRC=DEST`` and ``--exclude SRC`` to vendor
pattern files the manifest leaves out, to a chosen destination, and to drop
files the manifest vendors, for one instance. The selection is recorded as a
per-pattern ``select:`` in ``runtime-lock.yaml`` and reapplied by ``update`` and
``restore``. A lock with a selection is written as ``version: 2``; one without
stays ``version: 1``, byte for byte. ibek releases that read only version 1
refuse a version 2 lock with "unsupported lock version 2". See
``docs/how-to/select-pattern-files.md`` (#378).

A standalone ``scripts/convert-runtime-lock.py`` rewrites a ``runtime-lock.yaml``
that is not in the ``version:``/``patterns:`` shape this ibek reads. Run it once
per destination, from an ``ibek`` checkout:
``uv run scripts/convert-runtime-lock.py <dest>/runtime-lock.yaml``; or from
anywhere, including a services repo with no ``ibek`` checkout, straight from its
raw URL:
``uv run https://raw.githubusercontent.com/epics-containers/ibek/main/scripts/convert-runtime-lock.py <dest>/runtime-lock.yaml``
(#363).

Changed
~~~~~~~

``runtime-lock.yaml`` refuses top-level keys other than ``version``,
``schema_url`` and ``patterns`` rather than ignoring them and dropping them on
the next save (#378, #375).

``ibek pattern check``/``add``/``update`` refuse a ``runtime-lock.yaml`` in any
format they do not recognise, rather than special-casing one earlier shape. If
you see "lock format not recognised", convert the lock with
``uv run scripts/convert-runtime-lock.py <lock>`` and retry (#363).

The ``pvi`` dependency floor is now ``0.14.1``, with no ceiling. Generated PVI
screens use pvi's updated widget styling (fonts, colours and layout), so the
test goldens under ``tests/samples/outputs`` were regenerated to match.

The ``pvi`` dependency floor is now ``0.14.2b1``. Each field of a generated
``$(P)PVI`` group now names itself as its ``+trigger``, matching the mapping
QSRV (pvxs) applies by default, so pvxs no longer logs "Group ...PVI defines
no +trigger mappings" for every PVI group at IOC start. The ``*.pvi.template``
test goldens under ``tests/samples/outputs`` were regenerated to match.

Fixed
~~~~~

A plain ``dest`` whose last part has a file extension, in a
``pattern add --include SRC=DEST`` or a manifest rule, is the destination file:
``--include 'sim/x_sim\.template=config/x.template'`` writes
``config/x.template``. Such a ``dest`` that matches more than one file is
refused. A ``dest`` ending in ``/`` is always a folder.

Re-adding or updating a pattern replaces that pattern's files whatever file and
folder shapes its previous file-set left, including a folder where the new
file-set writes a file and a file where it needs a folder. A path in the way
that holds files the pattern did not vendor is refused before anything is
written.

``ioc.subst`` rows for a database file shared by several entity models are now
written in the order of the file's headings. Previously each row followed its own
entity model's arg order, so values could land under the wrong heading when two
models listed the same args in a different order (#349).

Entity models that load the same database file with different sets of args no
longer stop generation with "do not match the args used by earlier entities".
``ioc.subst`` gets one ``file`` block per distinct set of args, each with its
own headings, so every entity keeps exactly its own args. Rows with the same
set of args share a block. The blocks for one file are written next to each
other, in the order each set first appears in the instance. ``msi`` accepts
repeated ``file`` blocks for the same template. This lets a module combine,
for example, a private base model and a public sibling with an extra object
reference parameter, both using ``args: {.*: }`` (#383).

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

``ibek pattern schema`` parses more image refs. A registry port such as
``localhost:5000/org/ioc-x-runtime:1.0`` is no longer read as the tag, and a
ref with no registry host such as ``epics-containers/ioc-x-runtime:1.0`` no
longer loses its org. A ``-linux`` architecture infix is stripped like
``-rtems-beatnik`` (part of #375).

The published schema cache is keyed on registry host, full image path and tag
(``<host>/<path>/<tag>.json``), so images with the same name on different
registries no longer share an entry. Entries in the old
``<org>__<repo>__<tag>.json`` layout are not read; each schema is downloaded
once more (part of #375).

Documentation
~~~~~~~~~~~~~

Replaced the maintained guides and references with compact documentation of
the CLI lifecycle, YAML and Jinja rendering, ibek-support Ansible recipes,
and ibek's role in epics-containers. Added runnable rendering tutorials and
documented the persistent schema cache used by ``ibek pattern`` (issue #365).

Published releases are listed on
`GitHub <https://github.com/epics-containers/ibek/releases>`_.
