## ibek/tests/samples/schemas

The files in this folder represent schemas as described in the following table.

When changes have been
made these will need regenerating in order for the tests to pass.

It is important to review the generated files since the tests will always pass
after regeneration is done even if the output is badly broken.

| file | for | regenerate with |
|------|-----|------------------|
|ibek.schema.json|global schema for all <SUPPORT_MODULE>.ibek.schema|pipenv run python ibek ibek-schema tests/samples/schemas/ibek.schema.json|
|pmac.schema.json|schema for pmac support module|pipenv run python ibek ioc-schema tests/samples/yaml/pmac.ibek.yaml tests/samples/schemas/pmac.schema.json|
