from pathlib import Path

from ruamel.yaml import YAML

from ibek.support import Support
from tests.samples.classes.pmac_support import SUPPORT

sample_yaml = Path(__file__).parent / "samples" / "yaml"


def test_deserialize_support() -> None:
    with open(sample_yaml / "pmac.ibek.yaml") as f:
        actual = Support.deserialize(YAML().load(f))
    assert actual == SUPPORT


# def test_format_script_on_entity() -> None:
#     with open(Path(__file__).parent / "yaml" / "pmac.ibek.yaml") as f:
#         actual = Support.deserialize(YAML().load(f))

#     pmacIP = actual.entities[1]
#     script = pmacIP.format_script(port="blah", IP="1.1.1.1")
#     assert script == "PMACAsynIPPort(blah, 1.1.1.1:1025)"
