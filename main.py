from ruamel.yaml import YAML
from lxml import etree

def DTDbuild(entities):
    max_len = max(len(name) for name in entities)
    lines = [f'<!DOCTYPE PLUGIN [']
    for name in entities:
        padding = ' ' * (max_len - len(name) + 2)
        lines.append(f'<!ENTITY {name}{padding}"{entities[name]}">')
    lines.append(']>')
    return "\n".join(lines)

def PLUGINbuild(entities):
    lines = '<PLUGIN'
    for name in entities:
        lines += (f' {name}=\"&{name};\"')
    lines += ('></PLUGIN>')
    return lines

with open("test.yaml") as f:
    data = YAML().load(f)

entities = data.get("ENTITIES", {})
dtd = DTDbuild(entities)
plugin = PLUGINbuild(entities)
xml = f'{dtd}{plugin}'

parser = etree.XMLParser(resolve_entities=False)
root = etree.fromstring(xml.encode(), parser)

with open(data['CHANGES'], "r") as file:
    changelog = file.read()

changes = etree.SubElement(root, "CHANGES")
changes.text = f"\n{changelog}\n"

for file in data['FILE']:
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
                with open(file[line], "r") as f:
                    content = f.read()
                inline = etree.Element("INLINE")
                inline.text = f"\n{content}\n"
                elem.append(inline)
            case "CDATA":
                with open(file[line], "r") as f:
                    content = f.read()
                inline = etree.Element("INLINE")
                inline.text = etree.CDATA(f"\n{content}\n")
                elem.append(inline)
    root.append(elem)
print(etree.tostring(root, pretty_print=True, xml_declaration=True, standalone=True, doctype=dtd, encoding="utf-8").decode())


