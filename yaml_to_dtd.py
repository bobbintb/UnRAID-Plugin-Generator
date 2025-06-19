# import yaml # Replaced by ruamel.yaml
from ruamel.yaml import YAML
from xml.sax.saxutils import quoteattr, escape as std_escape
import sys
import re

from xml.dom import minidom
from xml.parsers.expat import ExpatError

KNOWN_ENTITY_NAMES = []
_SORTED_KNOWN_ENTITY_NAMES_CACHE = []

def populate_known_entities(entities_dict):
    global KNOWN_ENTITY_NAMES, _SORTED_KNOWN_ENTITY_NAMES_CACHE
    if isinstance(entities_dict, dict):
        KNOWN_ENTITY_NAMES = [str(key) for key in entities_dict.keys()]
        _SORTED_KNOWN_ENTITY_NAMES_CACHE = sorted(KNOWN_ENTITY_NAMES, key=len, reverse=True)
    else:
        KNOWN_ENTITY_NAMES = []
        _SORTED_KNOWN_ENTITY_NAMES_CACHE = []

def smart_escape_preserving_embedded(text, is_attribute=False):
    text_str = str(text)
    if not _SORTED_KNOWN_ENTITY_NAMES_CACHE:
        escaped_text = text_str.replace("&", "&amp;")
        escaped_text = escaped_text.replace("<", "&lt;")
        escaped_text = escaped_text.replace(">", "&gt;")
        if is_attribute:
            escaped_text = escaped_text.replace("\"", "&quot;")
        return escaped_text

    entity_names_pattern_part = "|".join([re.escape(name) for name in _SORTED_KNOWN_ENTITY_NAMES_CACHE])
    if not entity_names_pattern_part:
        escaped_text = text_str.replace("&", "&amp;")
        escaped_text = escaped_text.replace("<", "&lt;")
        escaped_text = escaped_text.replace(">", "&gt;")
        if is_attribute:
            escaped_text = escaped_text.replace("\"", "&quot;")
        return escaped_text

    entity_regex = re.compile(f"&({entity_names_pattern_part});")
    processed_parts = []
    last_end = 0
    for match in entity_regex.finditer(text_str):
        start, end = match.span()
        non_entity_segment = text_str[last_end:start]
        escaped_segment = non_entity_segment.replace("&", "&amp;")
        escaped_segment = escaped_segment.replace("<", "&lt;")
        escaped_segment = escaped_segment.replace(">", "&gt;")
        if is_attribute:
            escaped_segment = escaped_segment.replace("\"", "&quot;")
        processed_parts.append(escaped_segment)
        processed_parts.append(match.group(0))
        last_end = end

    remaining_segment = text_str[last_end:]
    escaped_remaining_segment = remaining_segment.replace("&", "&amp;")
    escaped_remaining_segment = escaped_remaining_segment.replace("<", "&lt;")
    escaped_remaining_segment = escaped_remaining_segment.replace(">", "&gt;")
    if is_attribute:
        escaped_remaining_segment = escaped_remaining_segment.replace("\"", "&quot;")
    processed_parts.append(escaped_remaining_segment)
    return "".join(processed_parts)

def generate_dtd_entities(entities_dict):
    if not entities_dict: return []
    max_key_length = 0
    str_keys = [str(key) for key in entities_dict.keys()]
    if str_keys: max_key_length = max(len(key) for key in str_keys)

    dtd_entity_strings = []
    for key, value in entities_dict.items():
        # Use smart_escape_preserving_embedded for DTD values to preserve known entities within them.
        # is_attribute=True ensures quotes are handled if the DTD value itself contains quotes.
        value_str = smart_escape_preserving_embedded(value, is_attribute=True)
        padding = " " * (max_key_length - len(str(key)))
        dtd_entity_strings.append(f'<!ENTITY {str(key)}{padding} "{value_str}">')
    return dtd_entity_strings

def main():
    yaml_file_path = "test.yaml"
    entities_dict_from_yaml = {}
    data = None
    dtd_buffer = []
    # xml_elements_buffer was used for parts; now plugin_content_buffer used for content of PLUGIN

    yaml_parser = YAML(typ='rt')
    try:
        with open(yaml_file_path, 'r') as f: data = yaml_parser.load(f)
        if data and "ENTITIES" in data and isinstance(data["ENTITIES"], dict):
            entities_dict_from_yaml = data["ENTITIES"]
        # ... (error handling for ENTITIES and file ops as before) ...
        elif data and "ENTITIES" in data:
            print(f"Error: 'ENTITIES' key in {yaml_file_path} is not a dictionary.", file=sys.stderr)
        elif data:
            print(f"Error: 'ENTITIES' key not found in {yaml_file_path}.", file=sys.stderr)
        else:
            print(f"Error: No data loaded from {yaml_file_path} or data is empty.", file=sys.stderr)
            return
    except FileNotFoundError:
        print(f"Error: YAML file not found at {yaml_file_path}", file=sys.stderr)
        return
    except Exception as e:
        print(f"Error parsing YAML file '{yaml_file_path}': {e}", file=sys.stderr)
        return

    populate_known_entities(entities_dict_from_yaml)

    generated_dtds = generate_dtd_entities(entities_dict_from_yaml)
    dtd_buffer.append("<!DOCTYPE PLUGIN [")
    for entity_str in generated_dtds:
        dtd_buffer.append(f"  {entity_str}")
    dtd_buffer.append("]>")

    # Build XML string with DTD entities PRESERVED
    plugin_attributes_preserved = []
    for key, value in entities_dict_from_yaml.items():
        attr_name = str(key)
        escaped_value = smart_escape_preserving_embedded(value, is_attribute=True)
        plugin_attributes_preserved.append(f'{attr_name}="{escaped_value}"')

    plugin_tag_opening_str = "<PLUGIN>" # Default if no attributes
    if plugin_attributes_preserved:
        plugin_tag_opening_str = "<PLUGIN " + " ".join(plugin_attributes_preserved) + ">"

    plugin_content_buffer = []

    if data and "CHANGES" in data:
        changes_file_path = data["CHANGES"]
        if isinstance(changes_file_path, str):
            try:
                with open(changes_file_path, 'r') as f_changes: changes_content = f_changes.read()
                plugin_content_buffer.append("<CHANGES>")
                plugin_content_buffer.append(smart_escape_preserving_embedded(changes_content, is_attribute=False))
                plugin_content_buffer.append("</CHANGES>")
            # ... (error handling for CHANGES file as before) ...
            except FileNotFoundError:
                print(f"Error: Changes file '{changes_file_path}' specified in 'CHANGES' key not found.", file=sys.stderr)
            except Exception as e:
                print(f"Error reading changes file '{changes_file_path}': {e}", file=sys.stderr)
        else:
            print(f"Error: Value of 'CHANGES' key must be a string (filepath), but found {type(changes_file_path)}.", file=sys.stderr)


    if data and "FILE" in data and isinstance(data["FILE"], list):
        file_list = data["FILE"]
        for item_idx, file_item in enumerate(file_list):
            # ... (comment processing and empty item skipping as before) ...
            if not isinstance(file_item, dict):
                print(f"Warning: Item in FILE list is not a dictionary: {file_item}", file=sys.stderr)
                continue

            comment_str = None
            if item_idx in file_list.ca.items:
                comment_info_for_item = file_list.ca.items[item_idx]
                if comment_info_for_item and len(comment_info_for_item) > 1 and comment_info_for_item[1]:
                    comment_tokens = comment_info_for_item[1]
                    if comment_tokens:
                        raw_comment_text = "".join([ct.value for ct in comment_tokens]).strip()
                        if raw_comment_text.startswith("#"):
                            comment_text = raw_comment_text[1:].strip()
                            comment_str = f"<!-- {comment_text} -->"
            if comment_str: plugin_content_buffer.append(comment_str)

            if not file_item and not comment_str: continue

            attribute_strings, generic_child_tag_strings = [], []
            inline_key_info, cdata_key_info = None, None
            key_order_counter = 0

            for key, value in file_item.items():
                key_order_counter += 1; key_str = str(key)
                if key_str == 'INLINE': inline_key_info = {'path': str(value), 'order': key_order_counter}
                elif key_str == 'CDATA': cdata_key_info = {'path': str(value), 'order': key_order_counter}
                elif key_str.startswith('@'):
                    attribute_strings.append(f'{key_str[1:]}="{smart_escape_preserving_embedded(value, is_attribute=True)}"')
                else:
                    generic_child_tag_strings.append(f"<{key_str}>{smart_escape_preserving_embedded(value, is_attribute=False)}</{key_str}>")

            final_inline_tag_string = None
            file_item_identifier = f"item at index {item_idx}"
            current_attrs_dict = {k.split('=')[0]: k.split('=')[1][1:-1] for k in attribute_strings if '=' in k}
            if 'Name' in current_attrs_dict:
                 file_item_identifier = f"FILE item with @Name='{current_attrs_dict['Name']}'"

            use_cdata = False
            if inline_key_info and cdata_key_info:
                print(f"Warning: {file_item_identifier} has both INLINE and CDATA. Using last.", file=sys.stderr)
                if cdata_key_info['order'] > inline_key_info['order']: use_cdata = True
            elif cdata_key_info: use_cdata = True

            info_to_use = None
            if use_cdata: info_to_use = cdata_key_info
            elif inline_key_info: info_to_use = inline_key_info

            if info_to_use: # Process INLINE/CDATA content choice
                try:
                    with open(info_to_use['path'], 'r') as f_content: raw_content = f_content.read()
                    if use_cdata:
                        final_inline_tag_string = f"<INLINE><![CDATA[{raw_content}]]></INLINE>"
                    else:
                        final_inline_tag_string = f"<INLINE>{std_escape(raw_content)}</INLINE>"
                # ... (error handling for INLINE/CDATA file read as before) ...
                except FileNotFoundError:
                    err_type = "CDATA" if use_cdata else "INLINE"
                    error_val = smart_escape_preserving_embedded(info_to_use['path'], False)
                    raw_content = f"<!-- Error: {err_type} file not found: {error_val} -->"
                    if use_cdata: final_inline_tag_string = f"<INLINE><![CDATA[{raw_content}]]></INLINE>"
                    else: final_inline_tag_string = f"<INLINE>{raw_content}</INLINE>"
                except Exception as e:
                    err_type = "CDATA" if use_cdata else "INLINE"
                    path_val = smart_escape_preserving_embedded(info_to_use['path'], False)
                    e_val = smart_escape_preserving_embedded(str(e), False)
                    raw_content = f"<!-- Error reading {err_type} file {path_val}: {e_val} -->"
                    if use_cdata: final_inline_tag_string = f"<INLINE><![CDATA[{raw_content}]]></INLINE>"
                    else: final_inline_tag_string = f"<INLINE>{raw_content}</INLINE>"


            if final_inline_tag_string: generic_child_tag_strings.append(final_inline_tag_string)

            file_tag_parts = ["<FILE"]
            if attribute_strings: file_tag_parts.append(" " + " ".join(attribute_strings))
            if not generic_child_tag_strings:
                if attribute_strings or file_item: plugin_content_buffer.append("".join(file_tag_parts) + " />")
            else:
                file_tag_parts.extend([">", "".join(generic_child_tag_strings), "</FILE>"])
                plugin_content_buffer.append("".join(file_tag_parts))
    elif data and "FILE" in data:
        print(f"Error: 'FILE' key in {yaml_file_path} is not a list.", file=sys.stderr)

    # Combine plugin tag with its content that's already processed for entities by smart_escape_preserving_embedded
    full_xml_content_list_preserved = [plugin_tag_opening_str]
    full_xml_content_list_preserved.extend(plugin_content_buffer)
    full_xml_content_list_preserved.append("</PLUGIN>")

    plugin_xml_with_entities = "\n".join(full_xml_content_list_preserved)

    # REMOVE the pre-minidom entity resolution loop.
    # The string passed to minidom will now include the DTD and unresolved entities.
    # resolved_xml_string_for_minidom = xml_string_with_preserved_entities
    # if _SORTED_KNOWN_ENTITY_NAMES_CACHE and entities_dict_from_yaml:
    #    # ... (LOOP WAS HERE) ...

    dtd_string = "\n".join(dtd_buffer)
    string_for_minidom = dtd_string + "\n" + plugin_xml_with_entities

    final_xml_output_str = ""
    if string_for_minidom.strip():
        try:
            # Ensure minidom parses the DTD by using the full string_for_minidom
            dom = minidom.parseString(string_for_minidom)
            # Pretty-print starting from the document element (<PLUGIN>)
            pretty_xml_string = dom.documentElement.toprettyxml(indent="\t")
            final_xml_output_str = pretty_xml_string
        except ExpatError as e:
            print(f"Error: XML parsing failed during pretty-printing (entities might be unresolvable by minidom): {e}\nFalling back to non-pretty XML (with entities preserved).", file=sys.stderr)
            final_xml_output_str = plugin_xml_with_entities # Fallback to XML with entities, not DTD
        except Exception as e:
            print(f"Error: An unexpected error occurred during pretty-printing: {e}\nFalling back to non-pretty XML (with entities preserved).", file=sys.stderr)
            final_xml_output_str = plugin_xml_with_entities

    # Print DTD separately
    if dtd_string:
        print(dtd_string)
    # Print the (potentially pretty-printed) XML part
    if final_xml_output_str:
        print(final_xml_output_str)

if __name__ == "__main__":
    main()
