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
            # Skip if file_item is empty (e.g. a list item that's just a comment placeholder)
            if not file_item and not (item_idx in file_list.ca.items and file_list.ca.items[item_idx][1]): # ensure it's not just a comment
                 # If file_item is empty AND it doesn't have an associated comment, then skip.
                 # If it has a comment, it will be printed, and then we'd print an empty <FILE /> if we don't continue.
                 # The goal is to not print <FILE /> for truly empty items.
                 # A file_item that is just a comment in YAML (e.g. '- # Just a comment line') results in an empty file_item (None).
                 # In ruamel.yaml, an empty item in a sequence that only had a comment might result in file_item being None.
                 # The check `if not isinstance(file_item, dict)` handles `None` items.
                 # If file_item is an empty dict `{}`, it will not be skipped by `isinstance`.
                 if not file_item: # file_item is an empty dict {}
                    if not comment_str: # And no comment was printed for it
                        continue # Skip printing <FILE /> for a truly empty item {} that had no comment
                    # If there was a comment, an empty <FILE /> might be desired by some. For now, let's print it.

            attribute_strings = []
            child_tag_strings = []

            for key, value in file_item.items(): # Single loop for keys
                key_str = str(key) # Ensure key is a string
                if key_str.startswith('@'):
                    attr_name = key_str[1:]
                    attribute_strings.append(f"{attr_name}={quoteattr(str(value))}")
                else:
                    # This key is for a child tag
                    tag_name = key_str
                    if tag_name == "INLINE":
                        inline_file_path = str(value)
                        try:
                            with open(inline_file_path, 'r') as f_inline:
                                inline_content = f_inline.read()
                            escaped_content = escape(inline_content)
                            child_tag_strings.append(f"<INLINE>{escaped_content}</INLINE>")
                        except FileNotFoundError:
                            error_placeholder = f"<!-- Error: INLINE file not found: {escape(inline_file_path)} -->"
                            child_tag_strings.append(f"<INLINE>{error_placeholder}</INLINE>")
                        except Exception as e:
                            error_placeholder = f"<!-- Error reading INLINE file {escape(inline_file_path)}: {escape(str(e))} -->"
                            child_tag_strings.append(f"<INLINE>{error_placeholder}</INLINE>")
                    else: # Handles URL, MD5, and any other non-@ keys
                        escaped_content = escape(str(value))
                        child_tag_strings.append(f"<{tag_name}>{escaped_content}</{tag_name}>")

            # Construct and print the <FILE> tag
            file_tag_parts = ["<FILE"]
            if attribute_strings:
                file_tag_parts.append(" " + " ".join(attribute_strings))

            if not child_tag_strings:
                # If file_item was empty dict {} and no comment printed, we would have continued.
                # If file_item was not empty dict but resulted in no attributes and no children (e.g. only invalid keys),
                # it's an edge case. For now, if it's not an empty dict, print the tag.
                # The only way child_tag_strings and attribute_strings are empty is if file_item was empty or contained unknown key types.
                # If file_item is not empty, print the tag.
                if not file_item and not attribute_strings: # only print <FILE /> if it's truly an empty item from YAML that wasn't skipped
                     # This case should be rare if `if not file_item: continue` is active and effective for {}
                     # Let's rely on the fact that if file_item is not empty, something will be in attributes or children.
                     # If file_item was not empty, but yielded no attributes and no children (e.g. `{'!BADKEY': 'value'}`),
                     # then we'd print `<FILE />`. This seems acceptable.
                     pass # Avoid printing <FILE /> if there were no attributes AND the original item was empty.
                          # This is covered by the `if not file_item: continue` at the start of item processing for empty dicts.

                # The condition to print a self-closing tag is: there are attributes OR (it's not an empty item AND no children were formed).
                # More simply: if no children, it's self-closing. But only print if there's something to print (attributes or it was a non-empty map).
                if attribute_strings or file_item : # If there are attributes, or it was a non-empty map originally
                    file_tag_parts.append(" />")
                    print("".join(file_tag_parts))
                # If file_item was empty AND no attributes, AND no comment, it's skipped earlier.
                # If file_item was empty AND no attributes, BUT had a comment, the comment is printed, then nothing else. This is desired.

            else: # Has child tags
                file_tag_parts.append(">")
                file_tag_parts.append("".join(child_tag_strings))
                file_tag_parts.append("</FILE>")
                print("".join(file_tag_parts))

    elif data and "FILE" in data: # FILE key exists but is not a list
        print(f"Error: 'FILE' key in {yaml_file_path} exists but is not a list.", file=sys.stderr)


if __name__ == "__main__":
    main()
