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
- Every template either option keeps (a ``.template`` or ``.db`` file) brings
  along the pattern files it names in an msi ``include "file"`` line, and the
  files those include in turn: the pattern file at that path, or else every
  one with that base name. msi needs them to expand the template, and the
  support YAML does not name them. An included name no pattern file has is
  left to the image. Autosave request files are not paired with an included
  template: ``ibek runtime generate-autosave`` pairs them only with the
  database files the substitution file loads.
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

# The kept files whose msi ``include "file"`` lines are followed.
MSI_SUFFIXES = (".template", ".db")

# An msi include directive: ``include "file"`` at the start of a line.
_MSI_INCLUDE_RE = re.compile(r'^[ \t]*include[ \t]+"([^"]+)"', re.MULTILINE)

# A database file name holding Jinja is rendered per entity, so it names no one
# pattern file that could be selected ahead of time.
_JINJA_RE = re.compile(r"\{\{|\{%")


class _Model:
    """What one entity model loads: database files, pvi device file, sub-entities."""

    def __init__(self, databases: list[str], pvi: str | None, sub_types: list[str]):
        self.databases = databases
        self.pvi = pvi
        self.sub_types = sub_types


def _load_models(name: str, support_yamls: dict[str, Path]) -> dict[str, _Model]:
    """The entity models the pattern's support YAMLs define, by ``module.name``.

    Keyed by the module-qualified type an entity uses, so two support YAMLs of
    one pattern that declare models of the same name in different modules stay
    distinct.
    """
    models: dict[str, _Model] = {}
    for rel, path in sorted(support_yamls.items()):
        try:
            data = YAML(typ="safe").load(path)
        except (OSError, YAMLError) as exc:
            raise ManifestError(f"{name}: {rel} cannot be read: {exc}") from exc
        if not isinstance(data, dict):
            continue
        module = str(data.get("module") or "")
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
            models[f"{module}.{model['name']}"] = _Model(databases, pvi_path, sub_types)
    return models


def _resolve_model(requested: str, models: dict[str, _Model]) -> list[str]:
    """The qualified models ``requested`` names: ``module.name`` or ``name``."""
    if requested in models:
        return [requested]
    return [key for key in models if key.rpartition(".")[2] == requested]


def _models_closure(
    name: str, requested: Sequence[str], models: dict[str, _Model]
) -> list[str]:
    """The qualified ``requested`` models plus every model of this pattern they
    instantiate."""
    where = f"{name}: {RUNTIME_LOCK_NAME} select.models (--model):"
    resolved: list[str] = []
    unknown: list[str] = []
    for model in requested:
        keys = _resolve_model(model, models)
        if not keys:
            unknown.append(model)
        elif len(keys) > 1:
            raise ManifestError(
                f"{where} {model!r} names models of several modules "
                f"({', '.join(sorted(keys))}); give it as module.name"
            )
        else:
            resolved.extend(keys)
    if unknown:
        names = [key.rpartition(".")[2] for key in models]
        # plain names unless two modules share one
        listed = names if len(set(names)) == len(names) else list(models)
        available = ", ".join(sorted(listed)) or "none"
        raise ManifestError(
            f"{where} no entity model {', '.join(repr(m) for m in unknown)} in "
            f"the pattern's support YAML; its models are: {available}"
        )
    seen: list[str] = []
    pending = resolved
    while pending:
        model = pending.pop(0)
        if model in seen:
            continue
        seen.append(model)
        pending.extend(sub for sub in models[model].sub_types if sub in models)
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
    matches = _matches(file, vendored)
    if len(matches) > 1:
        raise ManifestError(
            f"{name}: entity model {model!r} loads {kind} {file!r}, which "
            f"matches several pattern files ({', '.join(matches)}); select them "
            "with --only instead"
        )
    return matches[0] if matches else None


def _matches(file: str, vendored: Sequence[str]) -> list[str]:
    """The vendored pattern files ``file`` names: the one at that
    pattern-relative path, or else every one with its base name."""
    if file in vendored:
        return [file]
    base = PurePosixPath(file).name
    return [rel for rel in vendored if PurePosixPath(rel).name == base]


def _with_includes(
    keep: set[str], by_rel: dict[str, Path], vendored: Sequence[str]
) -> set[str]:
    """``keep`` plus every pattern file its templates msi-include, transitively."""
    kept = set(keep)
    pending = sorted(rel for rel in keep if rel.endswith(MSI_SUFFIXES))
    scheduled = set(pending)
    while pending:
        rel = pending.pop()
        text = by_rel[rel].read_text(errors="replace")
        for file in _MSI_INCLUDE_RE.findall(text):
            for match in _matches(file, vendored):
                kept.add(match)
                if match not in scheduled:
                    scheduled.add(match)
                    pending.append(match)
    return kept


def _req_rels(database_rel: str, vendored: Sequence[str]) -> list[str]:
    """The autosave request files paired with a kept database file."""
    stem = PurePosixPath(database_rel).stem
    names = {f"{stem}_{suffix}.req" for suffix in AUTOSAVE_REQ_SUFFIXES}
    return [rel for rel in vendored if PurePosixPath(rel).name in names]


def narrow_plan(
    pattern_dir: Path, plan: list[tuple[Path, str]], select: Selection
) -> list[tuple[Path, str]]:
    """Keep the entries of ``plan`` that ``select.only`` / ``select.models`` name,
    and the pattern files their templates msi-include.

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
        models = _load_models(name, support_yamls)
        for key in _models_closure(name, select.models, models):
            model = key.rpartition(".")[2]
            for file in models[key].databases:
                rel = _pattern_rel(name, model, "database file", file, vendored)
                if rel is not None:
                    keep.add(rel)
                    keep.update(_req_rels(rel, vendored))
            pvi = models[key].pvi
            if pvi is not None:
                rel = _pattern_rel(name, model, "pvi device file", pvi, vendored)
                if rel is not None:
                    keep.add(rel)
        keep.update(rel for rel in vendored if rel.endswith(PROTOCOL_SUFFIXES))
    keep = _with_includes(keep, by_rel, vendored)

    includes = [re.compile(rule.src) for rule in select.include]
    return [
        (src, key)
        for src, key in plan
        if (rel := src.relative_to(pattern_dir).as_posix()) in keep
        or any(regex.fullmatch(rel) for regex in includes)
    ]
