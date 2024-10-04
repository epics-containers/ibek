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
    os.getenv("IBEK_SYSTEM_TESTING") != "true",
    reason="export IBEK_SYSTEM_TESTING=true",
)
@pytest.mark.skipif(
    os.getenv("REMOTE_CONTAINERS") == "true", reason="only run outside devcontainers"
)
def test_container_build_and_run(tmp_path: Path):
    """
    make sure that a container build works and that the container can run an IOC

    IMPORTANT: this test runs against the ibek-test-KEEP branch of the
    ioc-template-example project.

    To update - clone ioc-template-example repo, then:
      - 'copier update --trust'.
      - update the ibek-support submodule to the desired version.
      - update its requirements.txt to point a compatible (this) version of ibek
      - push the changes to ibek-test-KEEP branch.
      - verify that it's CI tests pass.
    """
    ioc = "ioc-template-example"

    # get the ioc-template-example generic container source latest
    os.chdir(tmp_path)
    run_command(f"git clone https://github.com/epics-containers/{ioc}")
    run_command(f"cd {ioc}")

    # patch the dockerfile to include this version of ibek
    ibek = Path(__file__).parent.parent
    shutil.copytree(ibek, tmp_path / ioc / "ibek")
    docker = tmp_path / ioc / "Dockerfile"
    text = docker.read_text()
    this_ibek = "COPY ibek ibek\nRUN pip install ./ibek"
    text = re.sub(r"RUN pip install.*\n", this_ibek, text)
    docker.write_text(text)
    print(text)

    # build the container with latest ibek and latest ibek-support
    os.chdir(ioc)
    run_command("git submodule update --init")
    # use the submodule version that comes with ibek-test-KEEP branch
    # so don't do the checkout below.
    # run_command("cd ibek-support && git checkout main")
    run_command("./build")

    # run the container test script
    run_command("./tests/run-tests.sh")
