
import ruamel.yaml

def read_yaml(file_path):
    yaml = ruamel.yaml.YAML(typ='rt')
    with open(file_path, 'r') as file:
        data = yaml.load(file)
    return data

data = read_yaml('bobbintb.system.dirt.yaml')
with open("CHANGELOG.md", "r") as file:
    changelog = file.read()

xml = "<?xml version='1.0' standalone='yes'?>\n\n<!DOCTYPE PLUGIN [\n"

entitiyLength=len(max(data['ENTITIES'], key=len))
for entity in data['ENTITIES']:
    xml += f'<!ENITITY {entity}  {" " * (entitiyLength - len(entity))}"{data['ENTITIES'][entity]}">\n'

xml += ']>\n\n<PLUGIN'

for entity in data['ENTITIES']:
    xml += f' {entity}="&{entity};"'
xml += f'>\n\n<CHANGES>\n{changelog}\n</CHANGES>\n\n'

for file in data['FILE']:
    file_entity = '<FILE'
    file_string = ''
    for item in file:
        if item.startswith('@'):
            file_entity += f' {item[1:]}="{file[item]}"'
            print(file_entity)
        elif item == 'INLINE':
            with open(file['INLINE'], 'r') as f:
                inline_content = f.read()
            if '@Name' in file:
                inline_content = f'<![CDATA[\n{inline_content}\n]]>'
            file_string += f'<INLINE>\n{inline_content}\n</INLINE>\n</FILE>\n\n'
    file_entity += f'>\n{file_string}'
    xml += file_entity
xml += f'</PLUGIN>'

with open("test.xml", "w") as f:
    f.write(xml)
