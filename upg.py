import argparse
import os
import sys
from ruamel.yaml import YAML
from lxml import etree


def read_yaml(yamlFile):
    try:
        with open(yamlFile) as f:
            yamldata = YAML().load(f)
    except Exception as e:
        print(f"Error reading {yamlFile}: {e}")
        sys.exit(1)
    return yamldata


def DTDbuild():
    max_len = max(len(name) for name in entities)
    lines = [f'<!DOCTYPE PLUGIN [']
    for name in entities:
        padding = ' ' * (max_len - len(name) + 2)
        lines.append(f'<!ENTITY {name}{padding}"{entities[name]}">')
    lines.append(']>')
    return "\n".join(lines)


def PLUGINbuild():
    lines = '<PLUGIN'
    for name in entities:
        lines += (f' {name}=\"&{name};\"')
    lines += ('></PLUGIN>')
    return lines


def CHANGESbuild():
    try:
        with open(data['CHANGES'], "r") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {data['CHANGES']}: {e}")
        sys.exit(1)
    return content


parser = argparse.ArgumentParser()
parser.add_argument("file")
args = parser.parse_args()
data = read_yaml(args.file)
name, ext = os.path.splitext(args.file)

entities = data.get("ENTITIES", {})
dtd = DTDbuild()
plugin = PLUGINbuild()
changelog = CHANGESbuild()

parser = etree.XMLParser(resolve_entities=False)
root = etree.fromstring(f'{dtd}{plugin}'.encode(), parser)

changes = etree.SubElement(root, "CHANGES")
changes.text = f"\n{changelog}\n"

for i, file in enumerate(data['FILE']):
    elem = etree.Element("FILE")
    if data['FILE'].ca.items[i][1][0].value:
        comment = etree.Comment(data['FILE'].ca.items[i][1][0].value[1:-1])
        root.append(comment)
    for line in file:
        match line:
            case l if l.startswith("@"):
                elem.set(line[1:], file[line])
            case "INLINE":
                try:
                    with open(file[line], "r") as f:
                        content = f.read()
                except Exception as e:
                    print(f"Error reading {file[line]}: {e}")
                    sys.exit(1)
                inline = etree.Element("INLINE")
                inline.text = f"\n{content}\n"
                elem.append(inline)
            case "CDATA":
                try:
                    with open(file[line], "r") as f:
                        content = f.read()
                except Exception as e:
                    print(f"Error reading {file[line]}: {e}")
                    sys.exit(1)
                inline = etree.Element("INLINE")
                inline.text = etree.CDATA(f"\n{content}\n")
                elem.append(inline)
            case _:
                e = etree.Element(line)
                e.text = None
                if file[line][1:-1] in entities:
                    file[line] = file[line][1:-1]
                e.append(etree.Entity(file[line]))
                elem.append(e)
    root.append(elem)
print(etree.tostring(root, pretty_print=True, xml_declaration=True, standalone=True, doctype=dtd, encoding="utf-8").decode())
with open(f"{name}.plg", "w", encoding="utf-8") as f:
    f.write(etree.tostring(root, pretty_print=True, xml_declaration=True, standalone=True, doctype=dtd, encoding="utf-8").decode())
