# import yaml # Replaced by ruamel.yaml
from ruamel.yaml import YAML
from xml.sax.saxutils import quoteattr, escape
import sys # For stderr

# Old commented out functions (yaml_to_dtd, _process_yaml_node) are removed for brevity
# as they are not relevant to the current task.

def generate_dtd_entities(entities_dict):
    """
    Generates DTD entity strings from a dictionary.
    Pads keys for visual alignment.
    """
    if not entities_dict:
        return []

    max_key_length = 0
    if entities_dict: # Ensure entities_dict is not empty before finding max length
        # Ensure all keys are strings before calling len()
        str_keys = [str(key) for key in entities_dict.keys()]
        if str_keys:
             max_key_length = max(len(key) for key in str_keys)

    dtd_entity_strings = []
    for key, value in entities_dict.items():
        value_str = str(value).replace('"', '&quot;')
        # Ensure key is string for padding calculation
        padding = " " * (max_key_length - len(str(key)))
        dtd_entity_strings.append(f'<!ENTITY {str(key)}{padding} "{value_str}">')
    return dtd_entity_strings

def main():
    yaml_file_path = "test.yaml"
    entities_dict = {} # Initialize to ensure it's always a dict
    data = None

    yaml_parser = YAML(typ='rt')
    try:
        with open(yaml_file_path, 'r') as f:
            data = yaml_parser.load(f)

        if data and "ENTITIES" in data and isinstance(data["ENTITIES"], dict):
            entities_dict = data["ENTITIES"]
        elif data and "ENTITIES" in data: # Exists but not a dict
            print(f"Error: 'ENTITIES' key in {yaml_file_path} is not a dictionary.", file=sys.stderr)
            # entities_dict remains {}
        elif data: # Data loaded but ENTITIES key missing
            print(f"Error: 'ENTITIES' key not found in {yaml_file_path}.", file=sys.stderr)
            # entities_dict remains {}
        else: # Data could not be loaded or is empty
            print(f"Error: No data loaded from {yaml_file_path} or data is empty.", file=sys.stderr)
            return # Critical error, cannot proceed

    except FileNotFoundError:
        print(f"Error: YAML file not found at {yaml_file_path}", file=sys.stderr)
        return
    except Exception as e:
        print(f"Error parsing YAML file '{yaml_file_path}': {e}", file=sys.stderr)
        return

    # Generate and print DTD Entities
    dtd_entities = generate_dtd_entities(entities_dict)
    print("<!DOCTYPE PLUGIN [")
    for entity_str in dtd_entities:
        print(f"  {entity_str}")
    print("]>")

    # Generate and print <PLUGIN> tag
    plugin_attributes = []
    for key in entities_dict.keys():
        plugin_attributes.append(f'{str(key)}="&{str(key)};"')
    plugin_tag_str = "<PLUGIN " + " ".join(plugin_attributes) + ">"
    print(plugin_tag_str)

    # Process <CHANGES> block
    if data and "CHANGES" in data:
        changes_file_path = data["CHANGES"]
        if isinstance(changes_file_path, str):
            try:
                with open(changes_file_path, 'r') as f_changes:
                    changes_content = f_changes.read()
                print("<CHANGES>")
                print(changes_content, end='')
                print("</CHANGES>")
            except FileNotFoundError:
                print(f"Error: Changes file '{changes_file_path}' specified in 'CHANGES' key not found.", file=sys.stderr)
            except Exception as e:
                print(f"Error reading changes file '{changes_file_path}': {e}", file=sys.stderr)
        else:
            print(f"Error: Value of 'CHANGES' key must be a string (filepath), but found {type(changes_file_path)}.", file=sys.stderr)

    # Process FILE list
    if data and "FILE" in data and isinstance(data["FILE"], list):
        file_list = data["FILE"] # This is a CommentedSeq
        for item_idx, file_item in enumerate(file_list):
            if not isinstance(file_item, dict): # In ruamel.yaml, dicts are CommentedMap
                print(f"Warning: Item in FILE list is not a dictionary: {file_item}", file=sys.stderr)
                continue

            comment_str = None
            # Try to get comments attached to the sequence item
            # file_list.ca.items is a dictionary where keys are item indices
            if item_idx in file_list.ca.items:
                comment_info_for_item = file_list.ca.items[item_idx]
                # comment_info_for_item can be a list: [comment_before_marker, comment_after_marker, comment_after_value, comment_on_next_line]
                # For comments like '- # Comment Text', it's typically after the marker. So, index [1].
                if comment_info_for_item and len(comment_info_for_item) > 1 and comment_info_for_item[1]:
                    comment_tokens = comment_info_for_item[1]
                    if comment_tokens:
                        # A comment might be a list of CommentToken objects
                        raw_comment_text = "".join([ct.value for ct in comment_tokens]).strip()
                        if raw_comment_text.startswith("#"):
                            comment_text = raw_comment_text[1:].strip()
                            comment_str = f"<!-- {comment_text} -->"

            if comment_str:
                print(comment_str)

            attributes = []
            has_at_keys = False # To track if any @-attributes were found
            attributes = [] # Reset for each file_item
            child_tag_strings = [] # To store <URL>, <MD5>, <INLINE> etc.

            # First pass: get @-attributes
            for key, value in file_item.items():
                if isinstance(key, str) and key.startswith('@'):
                    has_at_keys = True
                    attr_name = key[1:]
                    attributes.append(f"{attr_name}={quoteattr(str(value))}")

            # Second pass: get child tags (INLINE, URL, MD5, etc.)
            for key, value in file_item.items():
                if isinstance(key, str) and not key.startswith('@'):
                    key_name = str(key)
                    if key_name == "INLINE":
                        inline_file_path = str(value)
                        try:
                            with open(inline_file_path, 'r') as f_inline:
                                inline_content = f_inline.read()
                            escaped_inline_content = escape(inline_content)
                            child_tag_strings.append(f"<INLINE>{escaped_inline_content}</INLINE>")
                        except FileNotFoundError:
                            error_msg = f"<!-- Error: INLINE file not found: {inline_file_path} -->"
                            child_tag_strings.append(f"<INLINE>{error_msg}</INLINE>")
                        except Exception as e:
                            error_msg = f"<!-- Error reading INLINE file {inline_file_path}: {escape(str(e))} -->"
                            child_tag_strings.append(f"<INLINE>{error_msg}</INLINE>")
                    else: # Handles URL, MD5, and any other non-@ keys
                        escaped_value = escape(str(value))
                        child_tag_strings.append(f"<{key_name}>{escaped_value}</{key_name}>")

            # Construct and print the <FILE> tag
            file_tag_start = "<FILE"
            if attributes: # Only add a space if there are attributes
                file_tag_start += " " + " ".join(attributes)

            if not child_tag_strings: # No children, self-closing tag
                # Only print if there were actual attributes or if the item itself is not empty.
                # If file_item is empty, attributes list will be empty, has_at_keys false.
                # If file_item is not empty but no @keys, has_at_keys is false.
                # We print a <FILE /> tag if there are attributes.
                # If no attributes but other keys (which would become children), it won't be self-closing.
                # If truly empty or only non-@ non-child keys, it could be <FILE />.
                # The current logic will make it <FILE /> if attributes list is populated.
                # If attributes is empty AND child_tag_strings is empty, what to do?
                # The problem asks for <FILE ... /> if no INLINE/children.
                # This means if has_at_keys is true OR file_item is not empty (implying potential non-@ keys that didn't become children),
                # then a tag should be printed.
                # Let's simplify: if there are attributes, print. If no attributes but item exists, it implies non-@ keys
                # which are now handled as children. So if child_tag_strings is empty, AND attributes is empty,
                # we might print just "<FILE />" if the original item was not empty.
                # However, the logic for child_tag_strings now means any non-@ key becomes a child.
                # So, if file_item is not empty, either attributes or child_tag_strings will be populated.
                if not file_item: # if the original yaml item was empty {} or an empty list item - comment only.
                    continue # Don't print <FILE /> for a comment-only line.

                print(f"{file_tag_start} />")

            else: # Has child tags
                print(f"{file_tag_start}>{''.join(child_tag_strings)}</FILE>")

    elif data and "FILE" in data: # FILE key exists but is not a list
        print(f"Error: 'FILE' key in {yaml_file_path} exists but is not a list.", file=sys.stderr)


if __name__ == "__main__":
    main()
