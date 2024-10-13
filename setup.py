#!/usr/bin/env python3

import os
import platform
import sys
import sysconfig
from subprocess import check_call
from build_manpages import build_manpages, get_build_py_cmd, get_install_cmd
from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.egg_info import egg_info
from virtme_ng.version import get_version_string

os.environ["__VNG_LOCAL"] = "1"
VERSION = get_version_string()

# Source .config if it exists (where we can potentially defined config/build
# options)
if os.path.exists(".config"):
    with open(".config", "r", encoding="utf-8") as config_file:
        for line in config_file:
            key, value = line.strip().split("=")
            os.environ[key] = value

# Global variables to store custom build options (as env variables)
build_virtme_ng_init = int(os.environ.get("BUILD_VIRTME_NG_INIT", 0))

# Make sure virtme-ng-init submodule has been cloned
if build_virtme_ng_init and not os.path.exists("virtme_ng_init/Cargo.toml"):
    sys.stderr.write("WARNING: virtme-ng-init submodule not available, trying to clone it\n")
    check_call("git submodule update --init --recursive", shell=True)

# Always include standard site-packages to PYTHONPATH
os.environ['PYTHONPATH'] = sysconfig.get_paths()['purelib']


class BuildPy(build_py):
    def run(self):
        print(f"BUILD_VIRTME_NG_INIT: {build_virtme_ng_init}")
        # Build virtme-ng-init
        if build_virtme_ng_init:
            cwd = "virtme_ng_init"
            root = "../virtme/guest"
            args = ["cargo", "install", "--path", ".", "--root", root]
            if platform.system() == "Darwin":
                machine = platform.machine()
                if machine == "arm64":
                    machine = "aarch64"
                target = f"{machine}-unknown-linux-musl"
                args.extend([
                    "--target", target,
                    "--config", f"target.{target}.linker = \"rust-lld\"",
                ])
            check_call(args, cwd="virtme_ng_init")
            check_call(
                ["strip", os.path.join(root, "bin", "virtme-ng-init")],
                cwd=cwd,
            )

        # Run the rest of virtme-ng build
        build_py.run(self)


class EggInfo(egg_info):
    def run(self):
        # Initialize virtme guest binary directory
        guest_bin_dir = "virtme/guest/bin"
        if not os.path.exists(guest_bin_dir):
            os.mkdir(guest_bin_dir)

        # Install guest binaries
        if (build_virtme_ng_init and not os.path.exists("virtme/guest/bin/virtme-ng-init")):
            self.run_command("build")
        egg_info.run(self)


if sys.version_info < (3, 8):
    print("virtme-ng requires Python 3.8 or higher")
    sys.exit(1)

packages = [
    "virtme_ng",
    "virtme",
    "virtme.commands",
    "virtme.guest",
]

package_files = [
    "virtme-init",
    "virtme-udhcpc-script",
    "virtme-snapd-script",
    "virtme-sound-script",
]

if build_virtme_ng_init:
    package_files.append("bin/virtme-ng-init")
    packages.append("virtme.guest.bin")

data_files = [
    ("/etc", ["cfg/virtme-ng.conf"]),
]

setup(
    name="virtme-ng",
    version=VERSION,
    author="Andrea Righi",
    author_email="arighi@nvidia.com",
    description="Build and run a kernel inside a virtualized snapshot of your live system",
    url="https://github.com/arighi/virtme-ng",
    license="GPLv2",
    long_description=open(
        os.path.join(os.path.dirname(__file__), "README.md"), "r", encoding="utf-8"
    ).read(),
    long_description_content_type="text/markdown",
    install_requires=[
        'argcomplete',
        'requests',
        # `pkg_resources` is removed in python 3.12, moved to setuptools.
        #
        # TODO: replace pkg_resources with importlib. # pylint: disable=fixme
        'setuptools',
    ],
    entry_points={
        "console_scripts": [
            "vng = virtme_ng.run:main",
            "virtme-ng = virtme_ng.run:main",
            "virtme-run = virtme.commands.run:main",
            "virtme-configkernel = virtme.commands.configkernel:main",
            "virtme-mkinitramfs = virtme.commands.mkinitramfs:main",
        ]
    },
    cmdclass={
        "build_manpages": build_manpages,
        "build_py": get_build_py_cmd(BuildPy),
        "install": get_install_cmd(),
        "egg_info": EggInfo,
    },
    packages=packages,
    package_data={"virtme.guest": package_files},
    scripts=[
        "bin/virtme-prep-kdir-mods",
    ],
    include_package_data=True,
    classifiers=[
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: POSIX :: Linux",
    ],
    zip_safe=False,
)
