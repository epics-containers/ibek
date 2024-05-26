import os
import subprocess
from pathlib import Path
from typing import List


def expand_env_vars(tokens: List[str]):
    for i in range(len(tokens)):
        tokens[i] = os.path.expandvars(tokens[i])
    return tokens


def handle_command(context: Path, tokens: List[str], step, start):
    msg = f'step {step} {" ".join(tokens)}'
    docker_action = tokens[0]
    tokens = expand_env_vars(tokens)

    print("context,", context)

    if step < start and docker_action != "WORKDIR":
        print("SKIPPING: " + msg)
        return
    else:
        print(msg)

    if docker_action == "RUN":
        result = subprocess.call(["bash", "-c", " ".join(tokens[1:])])
        if result > 0:
            raise RuntimeError("RUN command failed")
    elif docker_action == "WORKDIR":
        folder = Path.cwd() / Path(tokens[1])
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
        os.chdir(tokens[1])
    elif docker_action == "COPY":
        print("COPY", tokens)
        # skipping because in devcontainer the project folder is already mounted
        # where the destination copy is supposed to go inside the container
    elif docker_action == "FROM":
        if "runtime_prep" in tokens:
            print("\n== Aborting before destructive runtime prep stage. ==\n")
            exit(0)


def build_dockerfile(dockerfile: Path, start: int, stop: int):
    index = 0
    step = 1

    if not dockerfile.exists():
        raise FileNotFoundError(
            "No Dockerfile. Run this command in the generic ioc root folder."
        )
    context = dockerfile.parent

    dockerfile_lines: List[str] = dockerfile.read_text().split("\n")

    stop = min(stop, len(dockerfile_lines))
    while index < len(dockerfile_lines):
        command = dockerfile_lines[index]
        while command.endswith("\\"):
            index += 1
            command = command[:-1] + dockerfile_lines[index]
        index += 1

        if command == "" or command.startswith("#"):
            continue

        handle_command(context, command.split(), step, start)
        step = step + 1
        if step > stop:
            break
