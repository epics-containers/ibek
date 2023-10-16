"""
A class for rendering a substitution file from multiple instantiations of
support module definitions
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from ibek.globals import render_with_utils
from ibek.ioc import IOC, Entity
from ibek.support import Database


class RenderDb:
    @dataclass
    class RenderDbTemplate:
        filename: str
        rows: List[List[str]]
        columns: List[int]

    def __init__(self, ioc_instance: IOC) -> None:
        self.ioc_instance = ioc_instance
        # a mapping from template file name to details of instances of that template
        self.render_templates: Dict[str, RenderDb.RenderDbTemplate] = {}

    def add_row(self, filename: str, args: Mapping[str, Any], entity: Entity) -> None:
        """
        Accumulate rows of arguments for each template file,
        Adding a new template file if it does not already exist.
        Convert all arguments to strings.
        """
        filename = render_with_utils(dict(entity), filename)

        if filename not in self.render_templates:
            # for new filenames create a new RenderDbTemplate entry
            headings = [str(i) for i in list(args.keys())]
            self.render_templates[filename] = RenderDb.RenderDbTemplate(
                filename=filename,
                rows=[headings],  # first row is the headings
                columns=[0] * len(args),
            )

        # Add a new row of argument values.
        # Note the case where no value was specified for the argument
        # meaning that the name is to be rendered in Jinja
        row = ["{{ %s }}" % k if v is None else v for k, v in args.items()]

        # render any Jinja fields in the arguments
        for i, line in enumerate(row):
            row[i] = render_with_utils(dict(entity), row[i])

        # save the new row
        self.render_templates[filename].rows.append(row)

    def parse_instances(self) -> None:
        """
        Gather the database template instantiations from all entities
        while validating the arguments
        """
        for entity in self.ioc_instance.entities:
            databases = entity.__definition__.databases

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
        database.file = database.file.strip("\n")

        for arg, value in database.args.items():
            if value is None:
                if arg not in entity.__dict__:
                    raise ValueError(
                        f"database arg '{arg}' in database template "
                        f"'{database.file}' not found in context"
                    )

        self.add_row(database.file, database.args, entity)

    def add_extra_databases(self, databases: List[Tuple[Database, Entity]]) -> None:
        """Add databases that are not part of Entity definitions

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
