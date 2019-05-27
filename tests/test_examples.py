# Copyright (c) 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import random
from glob import glob
from os import getenv, listdir, walk
from os.path import dirname, getsize, isdir, isfile, join, normpath

import pytest

from platformio import util
from platformio.managers.platform import PlatformFactory, PlatformManager
from platformio.project.config import ProjectConfig


def pytest_generate_tests(metafunc):
    if "pioproject_dir" not in metafunc.fixturenames:
        return
    examples_dirs = []

    # repo examples
    examples_dirs.append(normpath(join(dirname(__file__), "..", "examples")))

    # dev/platforms
    for manifest in PlatformManager().get_installed():
        p = PlatformFactory.newPlatform(manifest['__pkg_dir'])
        ignore_conds = [
            not p.is_embedded(),
            p.name == "ststm8",
            # issue with "version `CXXABI_1.3.9' not found (required by sdcc)"
            "linux" in util.get_systype() and p.name == "intel_mcs51"
        ]
        if any(ignore_conds):
            continue
        examples_dir = join(p.get_dir(), "examples")
        assert isdir(examples_dir)
        examples_dirs.append(examples_dir)

    project_dirs = []
    for examples_dir in examples_dirs:
        platform_examples = []
        for root, _, files in walk(examples_dir):
            if "platformio.ini" not in files or ".skiptest" in files:
                continue
            platform_examples.append(root)

        random.shuffle(platform_examples)

        if getenv("APPVEYOR"):
            # use only 1 example for AppVeyor CI
            project_dirs.append(platform_examples[0])
        else:
            # test random 3 examples
            project_dirs.extend(platform_examples[:3])

    metafunc.parametrize("pioproject_dir", sorted(project_dirs))


@pytest.mark.examples
def test_run(pioproject_dir):
    with util.cd(pioproject_dir):
        build_dir = util.get_projectbuild_dir()
        if isdir(build_dir):
            util.rmtree_(build_dir)

        env_names = ProjectConfig(join(pioproject_dir, "platformio.ini")).envs()
        result = util.exec_command(
            ["platformio", "run", "-e",
             random.choice(env_names)])
        if result['returncode'] != 0:
            pytest.fail(str(result))

        assert isdir(build_dir)

        # check .elf file
        for item in listdir(build_dir):
            if not isdir(item):
                continue
            assert isfile(join(build_dir, item, "firmware.elf"))
            # check .hex or .bin files
            firmwares = []
            for ext in ("bin", "hex"):
                firmwares += glob(join(build_dir, item, "firmware*.%s" % ext))
            if not firmwares:
                pytest.fail("Missed firmware file")
            for firmware in firmwares:
                assert getsize(firmware) > 0
