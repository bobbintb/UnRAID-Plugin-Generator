#!/usr/bin/python

import argparse
import hashlib
import os
import re
import shutil
import subprocess
from datetime import datetime

import requests
import ruamel.yaml
import xmltodict

def package_plugin():
    dest = f"../tmp/usr/local/emhttp/plugins/{data['ENTITIES']['name']}"
    os.makedirs(dest, exist_ok=True)
    print("Copying files to temporary folder to archive...")
    exclusions = {".*", "plugin.sh", "sh/"}
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in exclusions]
        for file in files:
            if file not in exclusions:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, ".")
                dest_path = os.path.join(dest, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(src_path, dest_path)
    os.chdir("../tmp")
    installdir = '../tmp/install/'
    os.makedirs(installdir, exist_ok=True)
    if os.path.exists("doinst.sh"):
        shutil.move(f"${dest}/doinst.sh", installdir)
    if os.path.exists("slack-desc"):
        shutil.move(f"${dest}/slack-desc", installdir)
    makepkg_cmd = f"makepkg ../{data['ENTITIES']['repo']}/{data['ENTITIES']['name']}.txz"
    subprocess.run(makepkg_cmd, input=b"n\n", shell=True, check=True)

    os.chdir("..")
    shutil.rmtree("tmp", ignore_errors=True)

    txz_path = f"./{data['ENTITIES']['repo']}/{data['ENTITIES']['name']}.txz"
    md5_hash = hashlib.md5()
    with open(txz_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)

    md5sum = md5_hash.hexdigest()
    print(f"Package hash: {md5sum}")
    return md5sum

def convert_bash_to_python(version, previous_version):
    if version == previous_version[:-1] and re.search(r'[a-zA-Z]$', previous_version):
        extracted_letter = previous_version[-1]
        print(f"Previous sub-version: {extracted_letter}")

        ascii_code = ord(extracted_letter)
        next_ascii_code = ascii_code + 1

        # Ensure we wrap around from 'z' to 'a' or 'Z' to 'A'
        if extracted_letter.islower():
            next_letter = chr((next_ascii_code - ord('a')) % 26 + ord('a'))
        else:
            next_letter = chr((next_ascii_code - ord('A')) % 26 + ord('A'))

        version += next_letter

    return version

def getver():
    plugin_url = data['ENTITIES']['pluginURL']

    def replace_entities(match):
        entity = match.group(1)
        return data['ENTITIES'].get(entity, f'&{entity};')
    resolved_url = re.sub(r'&(\w+);', replace_entities, plugin_url)

    response = requests.get(resolved_url)

    if response.status_code == 200:
        xml_content = response.text
        # print(xml_content)
        # Now xml_content contains the XML file in memory as a string
    else:
        print(f"Failed to download XML. Status code: {response.status_code}")

    previous_version = xmltodict.parse(xml_content)['PLUGIN']['@version']
    print(previous_version)

    version = datetime.today().strftime("%Y.%m.%d")
    print('test')


    if version == previous_version:
        version += "a"
        print(f"New version: {version}")

    new_version = convert_bash_to_python(version, previous_version)
    return (new_version)

def read_yaml(file_path):
    yaml = ruamel.yaml.YAML(typ='rt')
    with open(file_path, 'r') as file:
        data = yaml.load(file)
    return data

def replace_ampersand(text, exceptions):
    pattern = '&(?!(?:' + '|'.join(re.escape(e[1:]) for e in exceptions) + '))'
    return re.sub(pattern, '&amp;', text)

def main():
    data['ENTITIES']['version'] = getver()
    data['ENTITIES']['MD5'] = package_plugin()
    try:
        with open(data['CHANGES'], "r") as file:
            changelog = file.read()
    except Exception as e:
        print(f"Error: {e}")
        print(f"Current working directory: {os.getcwd()}")
    xml_string = "<?xml version='1.0' standalone='yes'?>\n\n<!DOCTYPE PLUGIN [\n"

    entitiyLength = len(max(data['ENTITIES'], key=len))
    for entity in data['ENTITIES']:
        xml_string += f'<!ENITITY {entity}  {" " * (entitiyLength - len(entity))}"{data['ENTITIES'][entity]}">\n'

    xml_string += ']>\n\n<PLUGIN'

    for entity in data['ENTITIES']:
        xml_string += f' {entity}="&{entity};"'
    xml_string += f'>\n\n<CHANGES>\n{changelog}\n</CHANGES>\n\n'

    for file in data['FILE']:
        file_entity = '<FILE'
        file_string = ''
        for item in file:
            if item.startswith('@'):
                file_entity += f' {item[1:]}="{file[item]}"'
            elif item == 'INLINE':
                with open(file['INLINE'], 'r') as f:
                    inline_content = f.read()
                    inline_content = replace_ampersand(inline_content, [f'&{item};' for item in data['ENTITIES']])
                if '@Name' in file:
                    inline_content = f'<![CDATA[\n{inline_content}\n]]>'
                file_string += f'<INLINE>\n{inline_content}\n</INLINE>\n</FILE>\n\n'
            else:
                file_string += f'<{item}>{file[item]}</{item}></FILE>\n\n'
        file_entity += f'>\n{file_string}'
        xml_string += file_entity
    xml_string += f'</PLUGIN>'
    return xml_string

parser = argparse.ArgumentParser()
parser.add_argument("arg")
args = parser.parse_args()

data = read_yaml(args.arg)
xml_output = main()

with open(f"{data['ENTITIES']['name']}.plg", "w") as f:
    f.write(xml_output)
