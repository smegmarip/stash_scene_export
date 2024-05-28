import json
import os
import glob
import sys
import subprocess

os.chdir(os.path.dirname(os.path.realpath(__file__)))

from common import (
    get_scenes_metadata,
    stash_log,
    exit_plugin,
    pluginhumanname,
    clear_tempdir,
    clear_logfile,
    OUTPUT_DIR,
)

try:
    from stashapi.stashapp import StashInterface
except ModuleNotFoundError:
    print(
        "You need to install the stashapp-tools (stashapi) python module. (CLI: pip install stashapp-tools)",
        file=sys.stderr,
    )


def main():
    """
    The main function is the entry point for this plugin.

    :return: A string
    :doc-author: Trelent
    """
    global stash

    json_input = json.loads(sys.stdin.read())
    FRAGMENT_SERVER = json_input["server_connection"]
    stash = StashInterface(FRAGMENT_SERVER)

    ARGS = False
    PLUGIN_ARGS = False

    # Task Button handling
    try:
        PLUGIN_ARGS = json_input["args"]["mode"]
        ARGS = json_input["args"]
    except:
        pass

    # Check if the directory exists
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        stash_log(f"directory: '{OUTPUT_DIR}' created.", lvl="debug")

    # Clear temp directory
    clear_tempdir()

    # Clear log file
    clear_logfile()

    if PLUGIN_ARGS:
        stash_log("--Starting " + pluginhumanname + " Plugin --", lvl="debug")

        if "exportAll" in PLUGIN_ARGS:
            stash_log("running exportAll", lvl="info")
            filepath = get_scenes_metadata(stash=stash)
            if filepath is not None:
                stash_log("sceneExport =", {"result": filepath}, lvl="info")
                exit_plugin(msg="ok")
            stash_log("sceneExport =", {"result": None}, lvl="info")

    exit_plugin(msg="ok")


if __name__ == "__main__":
    main()
