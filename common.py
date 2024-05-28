import os
import re
import subprocess
import sys
import json
import time
from urllib.parse import urlparse
import uuid
import requests
import warnings

import numpy as np
from typing import Any, List, Tuple
from glob import glob

try:
    import stashapi.log as log
    from stashapi.stashapp import StashInterface
except ModuleNotFoundError:
    print(
        "You need to install the stashapp-tools (stashapi) python module. (CLI: pip install stashapp-tools)",
        file=sys.stderr,
    )

plugincodename = "sceneexport"
pluginhumanname = "SceneExport"

# Configuration/settings file... because not everything can be easily built/controlled via the UI plugin settings
# If you don't need this level of configuration, just define the default_settings here directly in code,
#    and you can remove the _defaults.py file and the below code
if not os.path.exists("config.py"):
    with open(plugincodename + "_defaults.py", "r") as default:
        config_lines = default.readlines()
    with open("config.py", "w") as firstrun:
        firstrun.write("from " + plugincodename + "_defaults import *\n")
        for line in config_lines:
            if not line.startswith("##"):
                firstrun.write(f"#{line}")

import config

default_settings = config.default_settings

PLUGIN_NAME = f"[{pluginhumanname}] "
STASH_URL = default_settings["stash_url"]
STASH_TMP = default_settings["stash_tmpdir"]
STASH_LOGFILE = default_settings["stash_logfile"]
OUTPUT_DIR = default_settings["output_dir"]

warnings.filterwarnings("ignore")


def stash_log(*args, **kwargs):
    """
    The stash_log function is used to log messages from the script.

    :param *args: Pass in a list of arguments
    :param **kwargs: Pass in a dictionary of key-value pairs
    :return: The message
    :doc-author: Trelent
    """
    messages = []
    for input in args:
        if not isinstance(input, str):
            try:
                messages.append(json.dumps(input, default=default_json))
            except:
                continue
        else:
            messages.append(input)
    if len(messages) == 0:
        return

    lvl = kwargs["lvl"] if "lvl" in kwargs else "info"
    message = " ".join(messages)

    if lvl == "trace":
        log.LEVEL = log.StashLogLevel.TRACE
        log.trace(message)
    elif lvl == "debug":
        log.LEVEL = log.StashLogLevel.DEBUG
        log.debug(message)
    elif lvl == "info":
        log.LEVEL = log.StashLogLevel.INFO
        log.info(message)
    elif lvl == "warn":
        log.LEVEL = log.StashLogLevel.WARNING
        log.warning(message)
    elif lvl == "error":
        log.LEVEL = log.StashLogLevel.ERROR
        log.error(message)
    elif lvl == "result":
        log.result(message)
    elif lvl == "progress":
        try:
            progress = min(max(0, float(args[0])), 1)
            log.progress(str(progress))
        except:
            pass
    log.LEVEL = log.StashLogLevel.INFO


def default_json(t):
    """
    The default_json function is used to convert a Python object into a JSON string.
    The default_json function will be called on every object that is returned from the StashInterface class.
    This allows you to customize how objects are converted into JSON strings, and thus control what gets sent back to the client.

    :param t: Pass in the time
    :return: The string representation of the object t
    :doc-author: Trelent
    """
    return f"{t}"


def get_config_value(section, prop):
    """
    The get_config_value function is used to retrieve a value from the config.ini file.

    :param section: Specify the section of the config file to read from
    :param prop: Specify the property to get from the config file
    :return: The value of a property in the config file
    :doc-author: Trelent
    """
    global _config
    return _config.get(section=section, option=prop)


def exit_plugin(msg=None, err=None):
    """
    The exit_plugin function is used to exit the plugin and return a message to Stash.
    It takes two arguments: msg and err. If both are None, it will simply print &quot;plugin ended&quot; as the output message.
    If only one of them is None, it will print that argument as either an error or output message (depending on which one was not None).
    If both are not none, then it will print both messages in their respective fields.

    :param msg: Display a message to the user
    :param err: Print an error message
    :return: A json object with the following format:
    :doc-author: Trelent
    """
    if msg is None and err is None:
        msg = pluginhumanname + " plugin ended"
    output_json = {}
    if msg is not None:
        stash_log(f"{msg}", lvl="debug")
        output_json["output"] = msg
    if err is not None:
        stash_log(f"{err}", lvl="error")
        output_json["error"] = err
    print(json.dumps(output_json))
    sys.exit()


def save_json(data, filename: str = "scene_metadata.json"):
    """
    The save_json function takes a dictionary and saves it to a JSON file.

    :param data: dict: Pass in the data that will be saved to a json file
    :param filename: str: Specify the name of the file that will be saved
    :return: The file path of the saved json file
    :doc-author: Trelent
    """
    directory = OUTPUT_DIR if OUTPUT_DIR.endswith(os.path.sep) else (OUTPUT_DIR + os.path.sep)
    # Generate a unique filename
    file_path = f"{directory}{filename}"

    try:
        with open(file_path, "w") as local_file:
            json.dump(data, local_file)
        stash_log(f"Downloaded and saved file to {file_path}", lvl="debug")
    except requests.exceptions.RequestException as e:
        stash_log(f"Failed to download file: {e}", lvl="error")
        return None

    return file_path


def clear_tempdir():
    """
    The clear_tempdir function is used to clear the temporary directory of all files.
    This function is called when a user requests that the temp directory be cleared, or when an error occurs in which case it will attempt to clear the temp dir before exiting.

    :return: A boolean value
    :doc-author: Trelent
    """
    tmpdir = STASH_TMP if STASH_TMP.endswith(os.path.sep) else (STASH_TMP + os.path.sep)
    for f in glob(f"{tmpdir}*.jpg"):
        try:
            os.remove(f)
        except OSError as e:
            stash_log(f"could not remove {f}", lvl="error")
            continue
    stash_log("cleared temp directory.", lvl="debug")


def clear_logfile():
    """
    The clear_logfile function clears the logfile.

    :return: Nothing
    :doc-author: Trelent
    """
    if STASH_LOGFILE and os.path.exists(STASH_LOGFILE):
        with open(STASH_LOGFILE, "w") as file:
            pass


def get_scenes_metadata(stash: StashInterface):
    """
    The get_scenes_metadata function is used to extract metadata from the Stash API.
    It takes a stash object as an argument and returns a json file containing all of the metadata for each scene in Stash.


    :param stash: StashInterface: Pass the stashinterface object to the function
    :return: A list of dictionaries with the following keys:
    :doc-author: Trelent
    """
    total = 1
    counter = 0
    batch = 120
    results = []
    while True:
        counter += 1
        _current, scenes = stash.find_scenes(f={}, filter={"per_page": 120, "page": counter}, get_count=True)

        if counter == 1:
            total = int(_current)
            stash_log(f"found {total} scenes", lvl="info")

        _current = batch * (counter - 1)

        if _current >= total:
            break

        num_scenes = len(scenes)
        # stash_log("scenes", scenes, lvl="trace")
        stash_log(f"processing {num_scenes} / {_current} scenes", lvl="info")

        for i in range(num_scenes):
            scene = scenes[i]
            _current -= 1
            progress = (float(total) - float(_current)) / float(total)
            stash_log(progress, lvl="progress")

            results.append(extract_scene_metadata(scene))

        stash_log("--end of loop--", lvl="debug")

    ts = time.time()
    if results:
        return save_json(results, f"stash_metadata_{ts}.json")
    return None


def extract_scene_metadata(scene: dict):
    """
    The extract_scene_metadata function takes a scene dictionary as input and returns a new dictionary containing the following keys:
        id: The unique identifier for the scene.
        title: The title of the scene, or if no title is provided, then it will be set to filename.
        filename: The name of the file that contains this particular video clip.  This is extracted from path using os.path.basename().split(&quot;/&quot;)[-2].  Note that this assumes that all files are stored in subdirectories within your stash directory (e.g., /stash/scenes/&lt;filename&gt;).  If you have

    :param scene: dict: Pass in the scene dictionary
    :return: A dictionary with the scene's id, title, filename, duration and sprites
    :doc-author: Trelent
    """
    file = scene["files"][0]
    filename = os.path.basename(file["path"]).split("/")[-1]
    metadata = {
        "id": scene["id"],
        "title": scene["title"] if scene["title"] else filename,
        "filename": filename,
        "duration": file["duration"],
        "sprites": scene["paths"]["sprite"],
    }
    return metadata
