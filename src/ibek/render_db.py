"""
A class for rendering a substitution file from multiple instantiations of
support module yaml files.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ibek.entity_model import Database
from ibek.ioc import Entity
from ibek.utils import UTILS


def str_to_bool(v):
    return v.lower() in ("yes", "true", "1")


class RenderDb:
    @dataclass
    class RenderDbTemplate:
        filename: str
        rows: List[List[str]]
        columns: List[int]

    def __init__(self, entities: Sequence[Entity]) -> None:
        self.entities = entities
        # a mapping from template file name to details of instances of that template
        self.render_templates: Dict[str, RenderDb.RenderDbTemplate] = {}

    def add_row(self, filename: str, params: Mapping[str, Any], entity: Entity) -> None:
        """
        Accumulate rows of arguments for each template file,
        Adding a new template file if it does not already exist.
        Convert all arguments to strings.
        """
        filename = UTILS.render(dict(entity), filename)

        if filename not in self.render_templates:
            # for new filenames create a new RenderDbTemplate entry
            headings = [str(i) for i in list(params.keys())]
            self.render_templates[filename] = RenderDb.RenderDbTemplate(
                filename=filename,
                rows=[headings],  # first row is the headings
                columns=[0] * len(params),
            )

        # add a new row of argument values, rendering any Jinja template fields
        row = list(UTILS.render_map(dict(entity), params).values())

        # save the new row
        self.render_templates[filename].rows.append(row)

    def parse_instances(self) -> None:
        """
        Gather the database template instantiations from all entities
        while validating the arguments
        """
        for entity in self.entities:
            databases = entity._model.databases

            # Not all entities instantiate database templates
            if entity.entity_enabled and databases is not None:
                for database in databases:
                    self.add_database(database, entity)

    def add_database(self, database: Database, entity: Entity) -> None:
        """Validate database and add row using entity as context.

        Args:
            database: Database to add row for
            entity: Entity to use as context for Jinja template expansion

        """
        if str_to_bool(UTILS.render(entity, database.enabled)):
            database.file = database.file.strip("\n")

            parameters = entity.__dict__.keys()
            # take each database parameter and expand it into the set of
            # entity parameters that it matches using regex
            expanded_database_entries: dict[str, str | None] = {}
            for arg, value in database.args.items():
                if "*" in arg or "?" in arg:
                    # this is a regex - match the parameters to the regex
                    for parameter in parameters:
                        if re.match(arg, parameter):
                            # TODO - should we perform regex subst on the value as well?
                            expanded_database_entries[parameter] = value
                else:
                    # simple db argument name
                    expanded_database_entries[arg] = value

            for arg, value in expanded_database_entries.items():
                if value is None:
                    if arg not in entity.__dict__ and arg not in UTILS.variables:
                        raise ValueError(
                            f"database arg '{arg}' in database template "
                            f"'{database.file}' not found in context"
                        )

            self.add_row(database.file, expanded_database_entries, entity)

    def add_extra_databases(self, databases: List[Tuple[Database, Entity]]) -> None:
        """Add databases that are not part of EntityModels

        Args:
            databases: Databases to add, each mapped against an Entity to use as context

        """
        for database, entity in databases:
            self.add_database(database, entity)

    def align_columns(self) -> None:
        """
        Make sure columns will line up for each template file, also
        provide escaping for spaces and quotes
        """

        # first calculate the column width for each template
        # including escaping spaces and quotes
        for template in self.render_templates.values():
            for n, row in enumerate(template.rows):
                for i, arg in enumerate(row):
                    row[i] = f'"{row[i]}"'
                    if i < len(template.columns) - 1:
                        row[i] += ", "
                    template.columns[i] = max(template.columns[i], len(row[i]))

        # now pad each column to the maximum width
        for template in self.render_templates.values():
            for row in template.rows:
                for i, arg in enumerate(row):
                    row[i] = arg.ljust(template.columns[i])

    def render_database(
        self, extra_databases: Optional[List[Tuple[Database, Entity]]] = None
    ) -> Dict[str, List[str]]:
        """Render a database substitution file.

        Args:
            extra_databases: Databases to add that are not included on an Entity

        """
        extra_databases = [] if extra_databases is None else extra_databases

        self.parse_instances()
        self.add_extra_databases(extra_databases)
        self.align_columns()

        results = {}

        for template in self.render_templates.values():
            results[template.filename] = ["".join(row) for row in template.rows]

        return results
