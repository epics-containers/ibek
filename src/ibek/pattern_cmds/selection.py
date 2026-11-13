"""
Narrow a pattern's vendored file-set to named files or to named entity models.

A destination's ``select.only`` and ``select.models`` (``ibek pattern add
--only`` / ``--model``) keep a subset of the files the pattern's manifest
vendors; :func:`narrow_plan` applies them to the plan ``plan_vendor`` returns,
so every file kept lands where the manifest (or an ``include`` rule) puts it.

- The pattern's support YAML (``*.ibek.support.yaml``) is always kept, whole and
  unmodified, so its hash still matches the release.
- ``only`` names pattern-relative paths exactly. Each must be a file the
  manifest vendors.
- ``models`` names entity models from the support YAML. Each model's
  ``databases[].file`` entries and its ``pvi.yaml_path`` are kept, as are those
  of the models it instantiates through ``sub_entities``. Each is matched to the
  pattern file at that pattern-relative path, or else to the one pattern file
  with that base name; a name no pattern file has is left to the image. For each
  database file kept, its autosave request files ``<stem>_settings.req`` and
  ``<stem>_positions.req`` are kept too, which is how ``ibek runtime
  generate-autosave`` pairs them. ``models`` also keeps every protocol file
  (``*.proto``, ``*.protocol``) the manifest vendors: a StreamDevice template
  names its protocol inside an INP or OUT link, which the support YAML does not
  describe, and a manifest has no notion of a protocol destination, so protocol
  files are recognised by suffix.
- Files an ``include`` rule places are vendored whatever ``only`` and
  ``models`` say: an include is an explicit request for that file.

``models`` is resolved against the release being vendored, so ``update`` follows
a model whose database file is renamed; ``only`` is literal.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ibek.globals import RUNTIME_LOCK_NAME

from .lock import Selection
from .manifest import MANIFEST_NAME, SUPPORT_YAML_SUFFIX, ManifestError

PROTOCOL_SUFFIXES = (".proto", ".protocol")

# The autosave request files ``ibek runtime generate-autosave`` pairs with a
# database template ``<stem>.template``: ``<stem>_<suffix>.req``.
AUTOSAVE_REQ_SUFFIXES = ("settings", "positions")

# A database file name holding Jinja is rendered per entity, so it names no one
# pattern file that could be selected ahead of time.
_JINJA_RE = re.compile(r"\{\{|\{%")


class _Model:
    """What one entity model loads: database files, pvi device file, sub-entities."""

    def __init__(self, databases: list[str], pvi: str | None, sub_types: list[str]):
        self.databases = databases
        self.pvi = pvi
        self.sub_types = sub_types


def _load_models(
    name: str, support_yamls: dict[str, Path]
) -> tuple[dict[str, _Model], set[str]]:
    """The entity models the pattern's support YAMLs define, and their modules."""
    models: dict[str, _Model] = {}
    modules: set[str] = set()
    for rel, path in sorted(support_yamls.items()):
        try:
            data = YAML(typ="safe").load(path)
        except (OSError, YAMLError) as exc:
            raise ManifestError(f"{name}: {rel} cannot be read: {exc}") from exc
        if not isinstance(data, dict):
            continue
        if data.get("module"):
            modules.add(str(data["module"]))
        for model in data.get("entity_models") or []:
            if not isinstance(model, dict) or "name" not in model:
                continue
            databases = [
                str(db["file"])
                for db in model.get("databases") or []
                if isinstance(db, dict) and "file" in db
            ]
            sub_types = [
                str(sub["type"])
                for sub in model.get("sub_entities") or []
                if isinstance(sub, dict) and "type" in sub
            ]
            pvi = model.get("pvi")
            pvi_path = (
                str(pvi["yaml_path"])
                if isinstance(pvi, dict) and pvi.get("yaml_path")
                else None
            )
            models[str(model["name"])] = _Model(databases, pvi_path, sub_types)
    return models, modules


def _models_closure(
    name: str, requested: Sequence[str], models: dict[str, _Model], modules: set[str]
) -> list[str]:
    """``requested`` plus every model of this pattern they instantiate."""
    unknown = [model for model in requested if model not in models]
    if unknown:
        available = ", ".join(sorted(models)) or "none"
        raise ManifestError(
            f"{name}: {RUNTIME_LOCK_NAME} select.models (--model): no entity model "
            f"{', '.join(repr(m) for m in unknown)} in the pattern's support "
            f"YAML; its models are: {available}"
        )
    seen: list[str] = []
    pending = list(requested)
    while pending:
        model = pending.pop(0)
        if model in seen:
            continue
        seen.append(model)
        for sub_type in models[model].sub_types:
            module, _, sub_name = sub_type.rpartition(".")
            if module in modules and sub_name in models:
                pending.append(sub_name)
    return seen


def _pattern_rel(
    name: str, model: str, kind: str, file: str, vendored: Sequence[str]
) -> str | None:
    """The vendored pattern file a model's ``kind`` file names, if any."""
    if _JINJA_RE.search(file):
        raise ManifestError(
            f"{name}: entity model {model!r} loads {kind} {file!r}, which "
            "is a template expression and names no single pattern file; select "
            "its files with --only instead"
        )
    if file in vendored:
        return file
    base = PurePosixPath(file).name
    matches = [rel for rel in vendored if PurePosixPath(rel).name == base]
    if len(matches) > 1:
        raise ManifestError(
            f"{name}: entity model {model!r} loads {kind} {file!r}, which "
            f"matches several pattern files ({', '.join(matches)}); select them "
            "with --only instead"
        )
    return matches[0] if matches else None


def _req_rels(database_rel: str, vendored: Sequence[str]) -> list[str]:
    """The autosave request files paired with a kept database file."""
    stem = PurePosixPath(database_rel).stem
    names = {f"{stem}_{suffix}.req" for suffix in AUTOSAVE_REQ_SUFFIXES}
    return [rel for rel in vendored if PurePosixPath(rel).name in names]


def narrow_plan(
    pattern_dir: Path, plan: list[tuple[Path, str]], select: Selection
) -> list[tuple[Path, str]]:
    """Keep the entries of ``plan`` that ``select.only`` / ``select.models`` name.

    ``plan`` is ``plan_vendor``'s ``(source path, destination key)`` list for the
    same ``select``; the entries kept are returned in the same order, with the
    same destinations. A plan is returned unchanged when ``select`` narrows
    nothing.
    """
    if not select.narrows():
        return plan
    name = pattern_dir.name
    by_rel = {src.relative_to(pattern_dir).as_posix(): src for src, _ in plan}
    vendored = sorted(by_rel)
    support_yamls = {
        rel: src for rel, src in by_rel.items() if rel.endswith(SUPPORT_YAML_SUFFIX)
    }
    keep = set(support_yamls)

    missing = [rel for rel in select.only if rel not in by_rel]
    if missing:
        raise ManifestError(
            f"{name}: {RUNTIME_LOCK_NAME} select.only (--only): "
            f"{', '.join(repr(m) for m in missing)} is not a file this pattern "
            f"vendors (a file {MANIFEST_NAME} leaves out can be added with "
            f"--include SRC=DEST); it vendors: {', '.join(vendored)}"
        )
    keep.update(select.only)

    if select.models:
        models, modules = _load_models(name, support_yamls)
        for model in _models_closure(name, select.models, models, modules):
            for file in models[model].databases:
                rel = _pattern_rel(name, model, "database file", file, vendored)
                if rel is not None:
                    keep.add(rel)
                    keep.update(_req_rels(rel, vendored))
            pvi = models[model].pvi
            if pvi is not None:
                rel = _pattern_rel(name, model, "pvi device file", pvi, vendored)
                if rel is not None:
                    keep.add(rel)
        keep.update(rel for rel in vendored if rel.endswith(PROTOCOL_SUFFIXES))

    includes = [re.compile(rule.src) for rule in select.include]
    return [
        (src, key)
        for src, key in plan
        if (rel := src.relative_to(pattern_dir).as_posix()) in keep
        or any(regex.fullmatch(rel) for regex in includes)
    ]
