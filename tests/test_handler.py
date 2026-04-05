import argparse
import logging
import urllib.request
import urllib.error
import base64
import sys
import json
import time
import os
import xml.etree.ElementTree as ET
import xml.dom.minidom as doc
import uuid
import io
import pathlib

def parseEnv(env_path):
    if not os.path.exists(env_path):
        logging.warning(f".env file {env_path} not found.")
        return {}
    
    with open(env_path) as f:
        env_vals = {}
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            env_vals[key] = value
        return env_vals
            


class Config:
    def __init__(self):
        env_vals = parseEnv("config/local.env")

        for key in env_vals:
            setattr(self, key, env_vals[key])

class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[36m",     # Cyan
        logging.INFO: "\033[32m",      # Green
        logging.WARNING: "\033[33m",   # Yellow
        logging.ERROR: "\033[31m",     # Red
        logging.CRITICAL: "\033[41m",  # Red background
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"


def parseArgs():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-k",
        "--api-key",
        help="Path to a file containing your OpenCloud API Key. Or, if you don't care about brevity, the raw API key.",
        metavar="<API key or path to API key file>")
    parser.add_argument(
        "-p",
        "--place",
        help="Place to run unit tests on, make sure this is an empty place where you have nothing important, this script will destroy previously written data on that place.",
        metavar="<place to upload rbxlx data>"
    )
    parser.add_argument(
        "-u",
        "--universe",
        help="Universe to run unit tests on, make sure this is an empty universe where you have nothing important, this script will destroy previously written data on that universe.",
        metavar="<universe to upload rbxlx data>"
    )
    
    return parser.parse_args()

def makeRequest(url, headers, body=None):
    data = None
    if body is not None:
        if isinstance(body, str):
            data = body.encode('utf-8')  # only encode once
        else:
            data = body  # already bytes
    request = urllib.request.Request(url, data=data, headers=headers, method='GET' if body is None else 'POST')

    max_attempts = 3
    for i in range(max_attempts):
        try:
            return urllib.request.urlopen(request)
        except Exception as e:
            if 'certificate verify failed' in str(e):
                logging.error(f'{str(e)} - you may need to install python certificates, see https://stackoverflow.com/questions/27835619/urllib-and-ssl-certificate-verify-failed-error')
                sys.exit(1)
            if i == max_attempts - 1:
                raise e
            else:
                logging.info(f'Retrying error: {str(e)}')
                time.sleep(1)

def readFileExitOnFailure(path, file_description):
    try:
        with open(path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        logging.error(f'{file_description.capitalize()} file not found: {path}')
    except IsADirectoryError:
        logging.error(f"Invalid {file_description} file: {path} is a directory")
    except PermissionError:
        logging.error(f"Permission denied to read {file_description} file: {path}")
    sys.exit(1)

def loadAPIKey(api_key_arg: str):
    source = ''
    api_key_arg = api_key_arg.strip()
    source = f'file {api_key_arg}'
    if os.path.exists(source) and os.path.isfile(source):
        key = readFileExitOnFailure(api_key_arg, "API key").strip()
    else:
        key = api_key_arg

    try:
        base64.b64decode(key, validate=True)
        return key
    except Exception as e:
        logging.error(f"API key appears invalid (not valid base64, loaded from {source}): {str(e)}")
        sys.exit(1)

def createTask(api_key, script, universe_id, place_id, place_version):
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': api_key
    }
    data = {
        'script': script
    }
    url = f'https://apis.roblox.com/cloud/v2/universes/{universe_id}/places/{place_id}/'
    if place_version:
        url += f'versions/{place_version}/'
    url += 'luau-execution-session-tasks'

    try:
        response = makeRequest(url, headers=headers, body=json.dumps(data))
    except urllib.error.HTTPError as e:
        return {
            "error": True,
            "status": e.code,
            "body": e.fp.read()
        }

    task = json.loads(response.read())
    return {"error": False, "task": task}

def pollForTaskCompletion(api_key, path):
    headers = {
        'x-api-key': api_key
    }
    url = f"https://apis.roblox.com/cloud/v2/{path}"

    logging.info("Waiting for task to finish...")

    exhausted_time = 0
    while True:
        try:
            response = makeRequest(url, headers=headers)
        except urllib.error.HTTPError as e:
            logging.error(f'Get task request failed, response body:\n{e.fp.read()}')
            sys.exit(1)

        task = json.loads(response.read())
        if task['state'] != 'PROCESSING':
            sys.stderr.write('\n')
            sys.stderr.flush()
            return task
        else:
            if exhausted_time >= 20:
                logging.error("Task spent too long processing. Execution limit per minute likely exhausted. Try again later.")
                sys.exit(1)
            sys.stderr.write('.')
            sys.stderr.flush()
            time.sleep(1)
            exhausted_time += 1

def getTaskLogs(api_key, task_path):
    headers = {
        'x-api-key': api_key
    }
    url = f'https://apis.roblox.com/cloud/v2/{task_path}/logs'

    try:
        response = makeRequest(url, headers=headers)
    except urllib.error.HTTPError as e:
        logging.error(f'Get task logs request failed, response body:\n{e.fp.read()}')
        sys.exit(1)

    logs = json.loads(response.read())
    messages = logs['luauExecutionSessionTaskLogs'][0]['messages']
    return ''.join([m + "\n" for m in messages])

def parseLogs(logs):
    return logs #stub

def handleLogs(task, api_key, is_complete):
    logs = getTaskLogs(api_key, task['path'])
    parseLogs(logs)
    if logs:
        if is_complete:
            print("\n------------------------------------------\n")
            logging.info(f'Task prints:\n{logs.strip()}')
        else:
            logging.error(f'Task error:\n{logs.strip()}')

def handleResults(results):
    max_key_len = 0
    failed_tests = []
    for item in results:
        for key, _ in item.items():
            if len(key) >= max_key_len:
                max_key_len = len(key)

    for item in results:
        for key, result_table in item.items():
            if len(result_table) == 1:
                passed = True
            else:
                passed = result_table[0]
                fail_reason = result_table[1]
                failed_tests.append({key:result_table})
            
            if passed:
                msg = f"     {key}:"
            else:
                msg = f"  {key}:"
            msg += (" " * ((max_key_len - len(key)) + 5))
            if passed == False:
                logging.warning(f"{msg} Test failed, {fail_reason}.  ❌")
            else:
                logging.info(f"{msg} Test passed!  ✅")

    if len(failed_tests) == 0:
        return
    print("\n------------------------------------------\n")
    
    # Failure summary
    logging.info("Failure Summary:\n")
    for item in failed_tests:
        for key, result_table in item.items():
            error = result_table[2]
            fail_reason = result_table[1]
            if fail_reason == "runtime error":
                logging.warning(f"{key} error:")
            elif fail_reason == "did not meet pass conditions":
                logging.info(f"{key} condition mismatch:")
            logging.error(f"{error}\n\n")



def handleSuccess(task):
    output = task['output']
    if output['results']:
        logging.info("Test Results:")
        print("\n")
        handleResults(output['results'])
    else:
        logging.info('The task did not produce any results')

def buildRbxlx():
    roblox = ET.Element("roblox", {"xmlns:xmime": "http://www.w3.org/2005/05/xmlmime",
                                   "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                                   "xsi:noNamespaceSchemaLocation": "http://www.roblox.com/roblox.xsd",
                                   "version": "4"})

    ext1 = ET.SubElement(roblox, "External")
    ext1.text = "null"
    ext2 = ET.SubElement(roblox, "External")
    ext2.text = "nil"

    replicated_storage = ET.SubElement(roblox, "Item", {"class": "ReplicatedStorage",
                                                        "referent": "RBXA6BADA80F58140ED8AE33AC0064306E5"})
    properties = ET.SubElement(replicated_storage, "Properties")
    attributes_serialize = ET.SubElement(properties, "BinaryString", {"name": "AttributesSerialize"})
    capabilities = ET.SubElement(properties, "SecurityCapabilities", {"name": "Capabilities"})
    capabilities.text = "0"
    defines_capabilities = ET.SubElement(properties, "bool", {"name": "DefinesCapabilities"})
    defines_capabilities.text = "false"
    history_id = ET.SubElement(properties, "UniqueId", {"name": "HistoryId"})
    history_id.text = "00000000000000000000000000000000"
    name = ET.SubElement(properties, "string", {"name": "Name"})
    name.text = "ReplicatedStorage"
    source_asset_id = ET.SubElement(properties, "int64", {"name": "SourceAssetId"})
    source_asset_id.text = "-1"
    tags = ET.SubElement(properties, "BinaryString", {"name": "Tags"})
    unique_id = ET.SubElement(properties, "UniqueId", {"name": "UniqueId"})
    unique_id.text = str(uuid.uuid4().hex)

    tree = ET.ElementTree(roblox)
    return replicated_storage, tree
    

def buildScript(script_path: str, parent, script_name = None):
    if script_name is None:
        script_name: str = os.path.basename(script_path)
        if script_name.find(".server") != -1 or script_name.find(".client") != -1:
            logging.error(f"Invalid script, script is not a module script. Path:{script_path}")
        script_name = script_name.removesuffix('.luau').strip()


    src = readFileExitOnFailure(script_path, "script")

 
    if script_name == "init":
        for element in parent:
            if element.tag == "Properties":
                for prop in element:
                    if prop.get("name") == "Name":
                        script_name = prop.text
        if script_name == "ReplicatedStorage":
            script_name = "RecurseAudioEngine"
    
    ## return unparented element for script to later parent
    module = ET.SubElement(parent, "Item", {'class': 'ModuleScript', 'referent': "RBXB04A222E0AB64BFEB7396075A3173918"})
    properties = ET.SubElement(module, "Properties")
    name = ET.SubElement(properties, "string", {'name': 'Name'})
    name.text = script_name
    source = ET.SubElement(properties, "ProtectedString", {"name": "Source"})
    source.text = src

    linked_source = ET.SubElement(properties, "Content", {'name': 'LinkedSource'})
    script_guid = ET.SubElement(properties, "string", {"name": "ScriptGuid"})
    script_guid.text = str(uuid.uuid4()).upper()
    attributes_serialize = ET.SubElement(properties, "BinaryString", {"name": "AttributesSerialize"})
    capabilities = ET.SubElement(properties, "SecurityCapabilities", {"name": "Capabilities"})
    capabilities.text = "0"
    defines_capabilities = ET.SubElement(properties, "bool", {"name": "DefinesCapabilities"})
    defines_capabilities.text = "false"
    history_id = ET.SubElement(properties, "UniqueId", {'name': 'HistoryId'})
    history_id.text = "00000000000000000000000000000000"
    source_asset_id = ET.SubElement(properties, "int64", {'name': 'SourceAssetId'})
    source_asset_id.text = "-1"
    tags = ET.SubElement(properties, "BinaryString", {'name': 'Tags'})
    unique_id = ET.SubElement(properties, "UniqueId", {'name': 'UniqueId'})
    unique_id.text = str(uuid.uuid4().hex)

    return module

def buildRbxmx(rbxmx_path, parent):
    rbxmx_tree = ET.parse(rbxmx_path)
    rbxmx_root = rbxmx_tree.getroot()

    for element in rbxmx_root.findall("Item"):
        parent.append(element)


def buildFolder(folder_path, parent):
    folder_name = os.path.basename(folder_path)

    folder = ET.SubElement(parent, "Item", {"class": "Folder", "referent": "RBX08F3CE5517EA45A5885C9DD907A67003"})
    properties = ET.SubElement(folder, "Properties")
    attributes_serialize = ET.SubElement(properties, "BinaryString", {"name": "AttributesSerialize"})
    capabilities = ET.SubElement(properties, "SecurityCapabilities", {"name": "Capabilities"})
    capabilities.text = "0"
    defines_capabilities = ET.SubElement(properties, "bool", {"name": "DefinesCapabilities"})
    defines_capabilities.text = "false"
    history_id = ET.SubElement(properties, "UniqueId", {"name": "HistoryId"})
    history_id.text = "00000000000000000000000000000000"
    name = ET.SubElement(properties, "string", {"name": "Name"})
    name.text = folder_name
    source_asset_id = ET.SubElement(properties, "int64", {"name": "SourceAssetId"})
    source_asset_id.text = "-1"
    tags = ET.SubElement(properties, "BinaryString", {"name": "Tags"})
    unique_id = ET.SubElement(properties, "UniqueId", {"name": "UniqueId"})
    unique_id.text = str(uuid.uuid4().hex)

    return folder

    


# get CDATA with standard libs (it's stupid)
def imbueCdata(xml_path: str, tree):
    buffer = io.BytesIO()
    tree.write(buffer, encoding='utf-8', xml_declaration=True)
    xml_string = buffer.getvalue().decode('utf-8')

    # Parse with minidom
    dom = doc.parseString(xml_string)

    for node in dom.getElementsByTagName("ProtectedString"):
        if node.getAttribute("name") != "Source":
            continue

        cdata = ""
        if node.firstChild:
            cdata = node.firstChild.nodeValue
            node.removeChild(node.firstChild)

        cdata = dom.createCDATASection(cdata)
        node.appendChild(cdata)

    # Remove XML declaration
    xml_no_decl = dom.toxml(encoding="utf-8").decode("utf-8")
    if xml_no_decl.startswith("<?xml"):
        xml_no_decl = xml_no_decl.split("?>", 1)[1].lstrip()
        
    return xml_no_decl

def fNameToPath(f_name: str, root_name: str):
    return str(root_name)+"/"+f_name


def constructDirectory(directory_path: str, parent, directory_name = None):
    def constructFile(f, p):
        suffix = os.path.splitext(entry)[1]
        if suffix == ".luau":
            buildScript(f, p)
        elif suffix == ".rbxmx":
            buildRbxmx(f, p)
        elif suffix == ".rbxm":
            logging.error("Cannot reconstruct a .rbxm asset. Please resave it as a .rbxmx asset. Closing the program, consider this version to have failed testing.")
            sys.exit(1)

    try:
        entries = os.listdir(directory_path)
    except:
        logging.error("Directory not found: "+directory_path)
        return
    
    init_file = None
    for entry in entries:
        full_path = os.path.join(directory_path, entry)
        if os.path.splitext(full_path)[1] != ".luau":
            continue
        if os.path.isfile(full_path):
            f_name = os.path.basename(full_path).removesuffix(".luau")
            if f_name == "init":
                init_file = full_path
                break

    if init_file:
        current_parent = buildScript(
            init_file,
            parent,
            directory_name or os.path.basename(directory_path)
        )

        for entry in entries:
            if os.path.basename(entry).removesuffix(".luau") == "init":
                continue

            full_path = os.path.join(directory_path, entry)
            if os.path.isdir(full_path):
                constructDirectory(full_path, current_parent)
            else:
                constructFile(full_path, current_parent)
    else:
        current_parent = buildFolder(directory_path, parent)

        for entry in entries:
            full_path = os.path.join(directory_path, entry)
            if os.path.isdir(full_path):
                constructDirectory(full_path, current_parent)
            else:
                constructFile(full_path, current_parent)



if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler()
    formatter = ColorFormatter("%(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)


    if os.path.basename(os.getcwd()) != "RECURSE Audio Engine":
        p = pathlib.Path(__file__)
        os.chdir(str(p.parent.parent))

    args = parseArgs()
    config = Config()

    unloaded_api_key = args.api_key or getattr(config, "ROBLOX_API_KEY", None)
    universe = args.universe or getattr(config, "UNIVERSE_ID", None)
    place = args.place or getattr(config, "PLACE_ID", None)

    if unloaded_api_key == None or unloaded_api_key == "":
        logging.error("Program expects an API key to be passed on executiong using -k or filled in local.env under config")
        sys.exit(1)
    
    if universe == None or universe == "":
        logging.error("Program expects a universe ID to be passed on executiong using -u or filled in local.env under config")
        sys.exit(1)

    if place == None or place == "":
        logging.error("Program expects an place ID to be passed on executiong using -p or filled in local.env under config")
        sys.exit(1)



    api_key = loadAPIKey(unloaded_api_key)

    replicated_storage, tree = buildRbxlx()

    src_directory = None
    for dir in os.listdir(str(pathlib.Path(os.getcwd()))):
        if os.path.basename(dir) == "src":
            src_directory = pathlib.Path(dir)
            break

    if src_directory is None:
        logging.error('No "src" directory found under Current Working Directory.\n' \
        'Please make sure that the project is properly formatted.')
        sys.exit(1)

    entires = os.listdir()

    init_file = None

    constructDirectory("src", replicated_storage, "RecurseAudioEngine")

    xml_data = imbueCdata("test_place.rbxlx", tree)
    xml_buffer = io.BytesIO()
    xml_buffer.write(xml_data.encode('utf-8'))

    xml_upload_url = (
    f"https://apis.roblox.com/universes/v1/{universe}/places/{place}/versions?versionType=Saved"
    )

    xml_upload_headers = {
    "x-api-key": api_key,
    "Content-Type": "application/xml"  # required for .rbxlx
    }

    response = makeRequest(xml_upload_url, headers=xml_upload_headers, body=xml_data.encode("utf-8"))
    raw_response = response.read()
    response_code = response.getcode()

    logging.info("Uploading local disc .rbxlx file to Roblox...")

    if response_code == 200:
        version_info = json.loads(raw_response)
        version_number = version_info.get("versionNumber")
    else:
        logging.info("Upload failed!")
        logging.info(f"Status: {response_code}")
        logging.info(f"Response: {raw_response.decode()}")
        sys.exit(1)

    for f in os.listdir("tests"):
        if os.path.splitext(f)[1] != ".luau":
            continue

        attempts = 0
        script = readFileExitOnFailure(os.path.join("tests", f), "script")
        while True:
            attempts += 1
            logging.info(f"Sending request to execute {f}.")

            task_dict = createTask(api_key, script, universe, place, version_number)
            if task_dict.get("error") == True:
                if task_dict.get("status") == 404:
                    if attempts >= 10:
                        logging.error("Place version never became ready for execution. Closing program.")
                        sys.exit(1)
                    else:
                        logging.info("Place version not ready for task execution.\nRetrying . . .")
                        time.sleep(3)
                        continue
                else:
                    logging.error(f'Create task request failed, response body:\n{task_dict.get("body")}')
                    break
            else:
                task = task_dict.get("task")

                task = pollForTaskCompletion(api_key, task['path'])
                is_complete = task['state'] == 'COMPLETE'
                if is_complete:
                    handleSuccess(task)
                handleLogs(task, api_key, is_complete)
                break