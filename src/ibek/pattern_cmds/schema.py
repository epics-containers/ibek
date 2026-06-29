"""
Per-instance ``ioc.schema.json`` generation for IOC instances.

The schema for an instance is *self-contained*: ibek fetches the published base
schema for the instance's pinned image and programmatically merges the instance's
vendored / local support entities into the discriminated ``oneOf`` /
``discriminator.mapping`` / ``$defs``. The same function backs ``ibek pattern``,
pre-commit and CI.

If no published schema can be found for the instance's image, this is reported
and the schema is left untouched (not an error) — generic images that have not
published a schema release simply do not get editor validation.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from ruamel.yaml import YAML

from ibek.entity_factory import EntityFactory
from ibek.globals import IOC_SCHEMA_NAME
from ibek.ioc_factory import IocFactory

# Entity defs always present in a generated base schema; never re-copied on merge.
BUILTIN_DEFS = {"RepeatEntity", "Wait4IPEntity", "Wait4USBEntity"}

PUBLISHED_SCHEMA_ASSET = "ibek.ioc.schema.json"
SCHEMA_HEADER = f"# yaml-language-server: $schema=../{IOC_SCHEMA_NAME}"


class SchemaNotFoundError(Exception):
    """The published base schema for an image could not be located."""


# --------------------------------------------------------------------------- #
# image ref -> published release asset
# --------------------------------------------------------------------------- #
def resolve_image_ref(image: str) -> tuple[str, str, str]:
    """Map a container image ref to ``(org, repo, tag)``.

    ``ghcr.io/epics-containers/ioc-adsimdetector-runtime:2025.11.1`` ->
    ``("epics-containers", "ioc-adsimdetector", "2025.11.1")``.
    """
    ref = re.sub(r"^[a-z0-9.-]+/", "", image.strip())  # strip registry host
    repo_path, _, tag = ref.partition(":")
    if not tag:
        raise SchemaNotFoundError(f"image {image!r} has no tag")
    parts = repo_path.split("/")
    if len(parts) < 2:
        raise SchemaNotFoundError(f"cannot parse org/repo from image {image!r}")
    org, name = parts[0], parts[-1]
    # Strip the developer/runtime suffix and optional architecture infix.
    name = re.sub(r"(-rtems-beatnik)?(-developer|-runtime)$", "", name)
    return org, name, tag


def published_schema_url(image: str) -> str:
    """Build the GitHub release-asset URL for an image's published schema."""
    org, repo, tag = resolve_image_ref(image)
    return (
        f"https://github.com/{org}/{repo}/releases/download/{tag}/"
        f"{PUBLISHED_SCHEMA_ASSET}"
    )


def _cache_path(image: str) -> Path:
    org, repo, tag = resolve_image_ref(image)
    root = Path(
        os.getenv("IBEK_SCHEMA_CACHE", Path.home() / ".cache" / "ibek" / "schemas")
    )
    return root / f"{org}__{repo}__{tag}.json"


def _http_get(url: str) -> bytes:
    """Fetch ``url``; raise SchemaNotFound on any failure (monkeypatched in tests)."""
    try:
        with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
            return response.read()
    except (urllib.error.URLError, OSError) as exc:
        raise SchemaNotFoundError(f"could not fetch {url}: {exc}") from exc


def fetch_base_schema(image: str) -> dict:
    """Return the published base schema for ``image`` (cached per immutable tag)."""
    cache = _cache_path(image)
    if cache.exists():
        return json.loads(cache.read_text())
    url = published_schema_url(image)
    data = _http_get(url)
    try:
        schema = json.loads(data)
    except json.JSONDecodeError as exc:
        raise SchemaNotFoundError(f"{url} did not return JSON: {exc}") from exc
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(schema, indent=2))
    return schema


# --------------------------------------------------------------------------- #
# entity merge
# --------------------------------------------------------------------------- #
def generate_schema_dict(support_yamls: list[Path]) -> dict:
    """Generate the ibek IOC JSON schema for exactly ``support_yamls``."""
    entity_factory = EntityFactory()
    entity_models = entity_factory.make_entity_models(list(support_yamls))
    ioc_model = IocFactory().make_ioc_model(entity_models)
    return ioc_model.model_json_schema()


def _union_node(schema: dict) -> dict:
    """Return the discriminated-union node (handles inline and wrapper layouts)."""
    items = schema["properties"]["entities"]["items"]
    if "$ref" in items:
        ref = items["$ref"].split("/")[-1]
        return schema["$defs"][ref]
    return items


def _collect_refs(node: object, acc: set[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str) and "/$defs/" in value:
                acc.add(value.split("/")[-1])
            else:
                _collect_refs(value, acc)
    elif isinstance(node, list):
        for item in node:
            _collect_refs(item, acc)


def merge_entities(base: dict, support_yamls: list[Path]) -> dict:
    """Merge the entities defined by ``support_yamls`` into ``base`` in place.

    The extra entities (and the transitive closure of ``$defs`` they reference)
    are grafted into the base schema's ``oneOf`` / ``discriminator.mapping`` /
    ``$defs``. Built-ins and defs already present in the base are not duplicated.
    """
    if not support_yamls:
        return base

    extra = generate_schema_dict(support_yamls)
    base_union = _union_node(base)
    extra_union = _union_node(extra)
    base_defs = base.setdefault("$defs", {})
    extra_defs = extra.get("$defs", {})
    base_mapping = base_union["discriminator"]["mapping"]

    # New top-level entity types: in the extras' mapping, not built-in, not in base.
    new_entities = {
        disc: ref.split("/")[-1]
        for disc, ref in extra_union["discriminator"]["mapping"].items()
        if ref.split("/")[-1] not in BUILTIN_DEFS and disc not in base_mapping
    }

    # Transitive closure of $defs to copy (enums, nested entities, ...).
    needed: set[str] = set(new_entities.values())
    queue = list(needed)
    while queue:
        name = queue.pop()
        definition = extra_defs.get(name)
        if definition is None:
            continue
        refs: set[str] = set()
        _collect_refs(definition, refs)
        for ref in refs:
            if ref in BUILTIN_DEFS or ref in base_defs or ref in needed:
                continue
            needed.add(ref)
            queue.append(ref)

    # Copy and extend in sorted order so the produced schema is byte-stable
    # across runs (set/closure iteration order is otherwise non-deterministic,
    # which would make the CI/pre-commit schema-freshness diff fail spuriously).
    for name in sorted(needed):
        if name in extra_defs and name not in base_defs:
            base_defs[name] = extra_defs[name]

    for disc in sorted(new_entities):
        key = new_entities[disc]
        base_union["oneOf"].append({"$ref": f"#/$defs/{key}"})
        base_mapping[disc] = f"#/$defs/{key}"

    return base


# --------------------------------------------------------------------------- #
# instance schema
# --------------------------------------------------------------------------- #
# Instance image is pinned in ``values.yaml`` (helm) or ``compose.yml`` (compose).
IMAGE_SOURCES = ("values.yaml", "compose.yml", "compose.yaml")


def find_image(instance_dir: Path) -> str | None:
    """Find the IOC image ref in an instance's ``values.yaml`` or ``compose.yml``.

    Helm instances pin the image in ``values.yaml``; compose instances pin it in
    ``compose.yml`` / ``compose.yaml``. The first of these that exists is searched.
    """
    source = next(
        (
            instance_dir / name
            for name in IMAGE_SOURCES
            if (instance_dir / name).exists()
        ),
        None,
    )
    if source is None:
        return None
    data = YAML(typ="safe").load(source) or {}

    found: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "image" and isinstance(value, str):
                    found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    for image in found:
        if "/" in image and ":" in image and "REPLACE" not in image.upper():
            return image
    return None


def rewrite_ioc_yaml_header(ioc_yaml: Path) -> None:
    """Set ``ioc.yaml``'s first line to the sibling-schema language-server header."""
    if not ioc_yaml.exists():
        return
    lines = ioc_yaml.read_text().splitlines()
    if lines and lines[0].startswith("# yaml-language-server:"):
        lines[0] = SCHEMA_HEADER
    else:
        lines.insert(0, SCHEMA_HEADER)
    ioc_yaml.write_text("\n".join(lines) + "\n")


def generate_instance_schema(instance_dir: Path) -> bool:
    """Generate ``<instance>/ioc.schema.json`` and rewrite the ``ioc.yaml`` header.

    Returns True if a schema was written, False if the published base schema for
    the instance's image could not be found (reported, not an error).
    """
    config_dir = instance_dir / "config"
    image = find_image(instance_dir)
    if image is None:
        print(
            f"Schema not found for {instance_dir.name}: "
            "no published image pinned in values.yaml/compose.yml; "
            "skipping schema generation"
        )
        return False
    try:
        base = fetch_base_schema(image)
    except SchemaNotFoundError as exc:
        print(
            f"Schema not found for {instance_dir.name} (image {image}): {exc}; "
            "skipping schema generation"
        )
        return False

    support_yamls = sorted(config_dir.glob("*.ibek.support.yaml"))
    merged = merge_entities(base, support_yamls)

    schema_path = instance_dir / IOC_SCHEMA_NAME
    schema_path.write_text(json.dumps(merged, indent=2) + "\n")
    rewrite_ioc_yaml_header(config_dir / "ioc.yaml")
    return True
