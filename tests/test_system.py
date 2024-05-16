"""
some system tests
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


def run_command(command: str, error_OK=False, show=False):
    """
    Run a command and print the output to the console. Throw an exception on failure.
    """
    print(f"Running: {command}")

    p_result = subprocess.run(command, capture_output=True, shell=True)

    output = p_result.stdout.decode()
    error_out = p_result.stderr.decode()

    result = output + error_out

    if p_result.returncode != 0:
        msg = f"Command Failed: {command}\n\n{result}\n\n\n"
        raise RuntimeError(msg)

    print(result)


@pytest.mark.skipif(
    os.getenv("REMOTE_CONTAINERS") == "true", reason="only run outside devcontainers"
)
def test_container_build_and_run(tmp_path: Path):
    """
    make sure that a container build works and that the container can run an IOC
    """
    ils = "ioc-lakeshore340"

    # get the lakeshore generic container source
    os.chdir(tmp_path)
    run_command(f"git clone https://github.com/epics-containers/{ils}")

    # patch the dockerfile to include this version of ibek
    ibek = Path(__file__).parent.parent
    shutil.copytree(ibek, tmp_path / ils / "ibek")
    docker = tmp_path / ils / "Dockerfile"
    text = docker.read_text()
    this_ibek = "COPY ibek ibek\nRUN pip install ./ibek"
    text = re.sub(r"RUN pip install.*\n", this_ibek, text)
    docker.write_text(text)
    print(text)

    # build the container with latest ibek and latest ibek-support
    os.chdir(ils)
    run_command("git submodule update --init")
    run_command("cd ibek-support && git checkout main")
    run_command("./build")

    # run the container test script
    run_command("./tests/run-tests.sh")
