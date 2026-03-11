"""
A built in entity model instance for adding a device to be considered as part of the IOC startup process.
This allows the IOC startup process to pause until communication with the specified devices is established,
which can help prevent issues with devices not being ready when the IOC starts.
(e.g used to detect motion controller on the network or mounted usb devices)
"""

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from ruamel.yaml import YAML, CommentedMap

from ibek.globals import GLOBALS
from ibek.ioc import BuiltInEntity

WAIT4IP_TYPE = "ibek.wait_ip"
WAIT4USB_TYPE = "ibek.wait_usb"


class Wait4IPModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    type: str
    device: str
    address: str
    timeout: int


class Wait4USBModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    type: str
    device: str
    id: str
    timeout: int


class DoWaitEntity(BuiltInEntity):
    """
    A definition of DoWaitEntity for the type checker.

    This is not really used - instead the dynamic class created
    by the make_entity_models function is used.
    """

    type: str = "ibek.do_wait"
    device: str = Field(
        description="The device name to use in the database record.",
        default="DEVICE",
    )
    timeout: int = Field(
        description="The number of seconds to wait for a response before considering the communication attempt a failure "
        "and exiting the IOC startup process; this will trigger a restart of the IOC pod by Kubernetes.\n"
        "A value of 0 means to wait indefinitely until communication is established.",
        default=0,
    )

    def _process_entity(self, output: Path = GLOBALS.RUNTIME_OUTPUT):
        pass


class Wait4USBEntity(DoWaitEntity):
    """
    A definition of Wait4USBEntity for the type checker.

    This is not really used - instead the dynamic class created
    by the make_entity_models function is used.
    """

    type: Literal["ibek.wait_usb"] = WAIT4USB_TYPE  # type: ignore[assignment]
    id: str = Field(
        description="The ID of the USB device to wait for. "
        "This should be in the format 'vendor_id:product_id', where vendor_id and product_id are the hexadecimal IDs of the USB device. "
        "For example, '1234:5678'.",
    )

    def _process_entity(self, output: Path = GLOBALS.RUNTIME_OUTPUT):
        """
        Not implemented yet - this will likely involve writing the USB device ID to a file in the runtime directory,
        for external tooling to parse and use to detect when the device is present.
        """
        return super()._process_entity(output)


class Wait4IPEntity(DoWaitEntity):
    """
    A definition of Wait4IPEntity for the type checker.

    This is not really used - instead the dynamic class is created
    by the make_entity_models function is used.
    """

    type: Literal["ibek.wait_ip"] = WAIT4IP_TYPE  # type: ignore[assignment]
    address: str = Field(
        description="The IP address and port to check communication with.",
    )

    def _process_entity(self, output: Path = GLOBALS.RUNTIME_OUTPUT):
        """
        Write the entity parameters into a YAML list file under the runtime directory.
        The file is created if it doesn't already exist and any previous entries are preserved.
        This makes it easy for external tooling to parse the list of addresses that need waiting for.
        """
        # Make sure the runtime directory exists
        output.mkdir(parents=True, exist_ok=True)

        # Create the YAML file path and initialize it with a header if it doesn't exist
        yaml_path = output / "wait_list.yaml"
        yaml_path.parent.mkdir(parents=True, exist_ok=True)

        # Configure the YAML dumper to produce a more human-readable format.
        yaml = YAML()
        yaml.explicit_end = False
        yaml.default_flow_style = False
        yaml.indent(mapping=2, sequence=4, offset=2)

        def improve_readability(yaml) -> str:
            """
            A transform function to improve the readability of the generated YAML file \
                by adding exactly one blank line before each list entry.
            The regex call is idempotent to avoid adding multiple blank lines on subsequent writes.
            """
            return re.sub(r"\n+  - type", "\n\n  - type", yaml)

        # Determine whether to write the header comment and to load existing data.
        if yaml_path.exists():
            header_needed = False
            # Load existing data from the YAML file, or initialize an empty list if the file is empty
            data = yaml.load(yaml_path) or []
        else:
            header_needed = True
            data = []

        # Using the Pydantic model to create the entry ensures that it adheres to the defined schema
        # and allows for any necessary validation or transformation of the data.
        entry = Wait4IPModel(
            type=self.type,
            device=self.device,
            address=self.address,
            timeout=self.timeout,
        ).model_dump()

        # Use CommentedMap to preserve the order of keys and allow for future comments if needed
        yaml_map = CommentedMap(entry)

        # Append the new entry to the data list, which will be written back to the YAML file.
        # This preserves any existing entries.
        data.append(yaml_map)

        header_comment = (
            "#######################################################################################\n"
            "# List of hardware to wait for communication with before proceeding with the IOC start.\n"
            "# This file is generated by DoWaitEntity._process_entity.\n"
            "#######################################################################################\n\n"
        )

        # Write the updated data back to the YAML file, including the header comment if needed.
        with yaml_path.open("w") as stream:
            if header_needed:
                stream.write(header_comment)
            yaml.dump(
                data,
                stream,
                transform=improve_readability,
            )
