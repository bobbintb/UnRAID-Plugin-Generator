import hashlib
import re
import urllib.request
from ruamel.yaml import YAML
from lxml import etree
from datetime import datetime

def determine_new_version(previous_version):
    version = datetime.today().strftime("%Y.%m.%d")
    if version == previous_version:
        version += "a"
    elif version == previous_version[:-1] and re.search(r'[a-zA-Z]$', previous_version):
        extracted_letter = previous_version[-1]
        ascii_code = ord(extracted_letter)
        next_ascii_code = ascii_code + 1
        if extracted_letter.islower():
            next_letter = chr((next_ascii_code - ord('a')) % 26 + ord('a'))
        else:
            next_letter = chr((next_ascii_code - ord('A')) % 26 + ord('A'))
        version += next_letter
    return version

def resolve_entity(entities, entity):
    s = entities[entity]
    while True:
        t = re.sub(r'&(\w+);', lambda m: str(entities[m.group(1)]), s)
        if t == s:
            return t
        s = t

def create_MD5_entity(entities):
    print("    No \"MD5\" entity found in YAML file. Downloading source package to get MD5 hash...", end=" ")
    full_url = resolve_entity(entities, "packageURL")
    source_file = urllib.request.urlopen(full_url).read()
    md5hash = hashlib.md5(source_file).hexdigest()
    entities["MD5"] = md5hash
    print("done.")

def create_version_entity(entities):
    print("    No \"version\" entity found in YAML file. Determining version...", end=" ")
    full_url = resolve_entity(entities, "pluginURL")
    plg_file = urllib.request.urlopen(full_url).read()
    plgparser = etree.XMLParser(load_dtd=True)
    plgroot = etree.fromstring(plg_file, plgparser)
    previous_version = plgroot.get('version')
    entities["version"] = determine_new_version(previous_version)
    print("done.")


def build_dtd(entities):
    max_len = max(len(name) for name in entities)
    lines = [f'<!DOCTYPE PLUGIN [']
    if "MD5" not in entities:
        create_MD5_entity(entities)
    if "version" not in entities:
        create_version_entity(entities)
    for name in entities:
        print(f"    Parsing {name} entity...", end=" ")
        padding = ' ' * (max_len - len(name) + 2)
        lines.append(f'<!ENTITY {name}{padding}"{entities[name]}">')
        print("done.")
    lines.append(']>')
    return "\n".join(lines)

def build_plugin(entities):
    lines = '<PLUGIN'
    for name in entities:
        lines += f' {name}=\"&{name};\"'
    lines += '></PLUGIN>'
    return lines

def build_changelog(changelogfile):
    with open(changelogfile, "r") as file:
        changelog = file.read()
    changes = etree.SubElement(root, "CHANGES")
    changes.text = changelog

def build_files(files):
    for file in files:
        elem = etree.Element("FILE")
        for line in file:
            match line:
                case l if l.startswith("@"):
                    elem.set(line[1:], file[line])
                case l if l.startswith("#"):
                    print(l)
                    elem.set(line[1:], file[line])

                    comment = etree.Comment("your comment text")
                    elem.append(comment)

                case "INLINE":
                    print(f"        {file[line]}...", end=" ")
                    with open(file[line], "r") as f:
                        content = f.read()
                    inline = etree.Element("INLINE")
                    inline.text = content
                    elem.append(inline)
                    print("done.")
                case "CDATA":
                    print(f"        {file[line]}...", end=" ")
                    with open(file[line], "r") as f:
                        content = f.read()
                    inline = etree.Element("INLINE")
                    inline.text = etree.CDATA(content)
                    elem.append(inline)
                    print("done.")
                case _:
                    inline = etree.Element(line)
                    inline.text = file[line]
                    elem.append(inline)
        root.append(elem)

with open("test.yaml") as f:
    data = YAML().load(f)

yamlentities = data.get("ENTITIES", {})

print("Creating DTD section...")
dtd = build_dtd(yamlentities)
print("    ...done.")

print("Creating PLUGIN section...", end=" ")
plugin = build_plugin(yamlentities)
print("done.")

xml = f'{dtd}{plugin}'

parser = etree.XMLParser(resolve_entities=False)
root = etree.fromstring(xml.encode(), parser)

print("    Parsing changelog...", end=" ")
build_changelog(data['CHANGES'])
print("done.")

print("    Parsing FILES...")
build_files(data['FILE'])
print("        ...done.")

print(etree.tostring(root, pretty_print=True, xml_declaration=True, standalone=True, doctype=dtd, encoding="utf-8").decode())


