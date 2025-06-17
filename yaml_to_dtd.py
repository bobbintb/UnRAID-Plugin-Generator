import yaml
# from xml.etree.ElementTree import Element, tostring # No longer needed
# import argparse # No longer needed

# def yaml_to_dtd(yaml_data):
#     """
#     Converts YAML data to DTD.
#     """
#     if not isinstance(yaml_data, dict):
#         raise ValueError("DTD generation requires a YAML dictionary as the root.")
#     if len(yaml_data.keys()) != 1:
#         raise ValueError("YAML must have a single root element for DTD conversion.")
#     root_element_name = list(yaml_data.keys())[0]
#     root_data = yaml_data[root_element_name]
#     dtd_elements = []
#     _process_yaml_node(root_element_name, root_data, dtd_elements)
#     return "\n".join(dtd_elements)

# def _process_yaml_node(element_name, node_data, dtd_elements):
#     """
#     Recursively processes a YAML node and generates DTD element declarations.
#     """
#     if isinstance(node_data, dict):
#         child_elements = []
#         for key, value in node_data.items():
#             child_elements.append(key)
#             _process_yaml_node(key, value, dtd_elements)
#         if child_elements:
#             children_str = ", ".join(child_elements)
#             dtd_elements.append(f"<!ELEMENT {element_name} ({children_str})>")
#         else:
#             dtd_elements.append(f"<!ELEMENT {element_name} ANY>")
#     elif isinstance(node_data, list):
#         if node_data:
#             if isinstance(node_data[0], dict):
#                 first_item = node_data[0]
#                 if len(first_item.keys()) == 1:
#                     list_item_element_name = list(first_item.keys())[0]
#                     _process_yaml_node(list_item_element_name, first_item[list_item_element_name], dtd_elements)
#                     dtd_elements.append(f"<!ELEMENT {element_name} ({list_item_element_name}+)>")
#                 else:
#                     if not any(e.startswith(f"<!ELEMENT {element_name} ") for e in dtd_elements):
#                         dtd_elements.append(f"<!ELEMENT {element_name} ANY>")
#             else:
#                 singular_name = element_name[:-1] if element_name.endswith('s') else f"{element_name}_item"
#                 if not any(e.startswith(f"<!ELEMENT {singular_name} ") for e in dtd_elements):
#                     dtd_elements.append(f"<!ELEMENT {singular_name} (#PCDATA)>")
#                 dtd_elements.append(f"<!ELEMENT {element_name} ({singular_name}+)>")
#         else:
#             if not any(e.startswith(f"<!ELEMENT {element_name} ") for e in dtd_elements):
#                  dtd_elements.append(f"<!ELEMENT {element_name} EMPTY>")
#     elif isinstance(node_data, (str, int, float, bool)):
#         if not any(e.startswith(f"<!ELEMENT {element_name} ") for e in dtd_elements):
#             dtd_elements.append(f"<!ELEMENT {element_name} (#PCDATA)>")
#     else:
#         if not any(e.startswith(f"<!ELEMENT {element_name} ") for e in dtd_elements):
#             dtd_elements.append(f"<!ELEMENT {element_name} ANY>")


def generate_dtd_entities(entities_dict):
    """
    Generates DTD entity strings from a dictionary.
    Pads keys for visual alignment.
    """
    if not entities_dict:
        return []

    max_key_length = 0
    if entities_dict: # Ensure entities_dict is not empty before finding max length
        max_key_length = max(len(key) for key in entities_dict.keys())

    dtd_entity_strings = []
    for key, value in entities_dict.items():
        # Ensure value is a string, escape special XML characters if necessary (though problem implies simple strings)
        # For DTD entities, quotes within the value string might need escaping depending on outer quotes.
        # Assuming values are simple strings as per example.
        value_str = str(value).replace('"', '&quot;') # Basic escaping for double quotes in value
        padding = " " * (max_key_length - len(key))
        dtd_entity_strings.append(f'<!ENTITY {key}{padding} "{value_str}">')
    return dtd_entity_strings

def main():
    yaml_file_path = "test.yaml"
    entities_dict = None

    try:
        with open(yaml_file_path, 'r') as f:
            data = yaml.safe_load(f)
            if data and "ENTITIES" in data:
                entities_dict = data["ENTITIES"]
            else:
                print(f"Error: 'ENTITIES' key not found in {yaml_file_path}")
                return
    except FileNotFoundError:
        print(f"Error: YAML file not found at {yaml_file_path}")
        return
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return

    if not isinstance(entities_dict, dict):
        print(f"Error: 'ENTITIES' key in {yaml_file_path} does not contain a dictionary.")
        return

    dtd_entities = generate_dtd_entities(entities_dict)

    print("<!DOCTYPE PLUGIN [")
    for entity_str in dtd_entities:
        print(f"  {entity_str}")
    print("]>")

    # Generate the <PLUGIN ...> tag
    plugin_attributes = []
    if entities_dict: # entities_dict would have been populated from try-except block
        for key in entities_dict.keys():
            plugin_attributes.append(f'{key}="&{key};"')

    plugin_tag_str = "<PLUGIN " + " ".join(plugin_attributes) + ">"
    print(plugin_tag_str)

    # Process <CHANGES> block
    if "CHANGES" in data: # 'data' holds the full parsed YAML
        changes_file_path = data["CHANGES"]
        if isinstance(changes_file_path, str):
            try:
                with open(changes_file_path, 'r') as f_changes:
                    changes_content = f_changes.read()

                print("<CHANGES>")
                print(changes_content, end='') # end='' to avoid double newline if content ends with one
                print("</CHANGES>")
            except FileNotFoundError:
                import sys
                print(f"Error: Changes file '{changes_file_path}' specified in 'CHANGES' key not found.", file=sys.stderr)
            except Exception as e:
                import sys
                print(f"Error reading changes file '{changes_file_path}': {e}", file=sys.stderr)
        else:
            import sys
            print(f"Error: Value of 'CHANGES' key must be a string (filepath), but found {type(changes_file_path)}.", file=sys.stderr)


if __name__ == "__main__":
    main()
