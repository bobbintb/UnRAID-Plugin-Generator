# import yaml # Replaced by ruamel.yaml
from ruamel.yaml import YAML
# Rename to avoid conflict
from xml.sax.saxutils import quoteattr, escape as std_escape
import sys  # For stderr
import re  # For smart_escape

# Global list for known entity names
KNOWN_ENTITY_NAMES = []

# Old commented out functions (yaml_to_dtd, _process_yaml_node) are removed for brevity
# as they are not relevant to the current task.


def populate_known_entities(entities_dict):
    global KNOWN_ENTITY_NAMES
    if isinstance(entities_dict, dict):
        KNOWN_ENTITY_NAMES = [str(key) for key in entities_dict.keys()]
    else:
        KNOWN_ENTITY_NAMES = []  # Ensure it's an empty list

# def smart_escape(text, is_attribute=False):
#     """
#     Escapes XML special characters in text. If text is already a valid entity reference,
#     it's returned unchanged.
#     """
#     text_str = str(text).strip() # Added .strip() for robustness
#     # Regex to check for common well-formed entity references (named, decimal, hex)
#     # Allows &name; &#123; &#xABC;
#     # It's a simplified check; a full XML parser's entity logic is more complex.
#     entity_pattern = r"^&[a-zA-Z_#][a-zA-Z0-9_#\.-]*;$" # Hyphen moved, dot escaped (though not strictly necessary in [])
#     if re.match(entity_pattern, text_str):
#         return text_str  # Already an entity, return as is
#
#     # Standard XML escaping for characters
#     # Must replace '&' first
#     text_str = text_str.replace("&", "&amp;")
#     text_str = text_str.replace("<", "&lt;")
#     text_str = text_str.replace(">", "&gt;")
#
#     if is_attribute:
#         text_str = text_str.replace("\"", "&quot;")
#         # For attributes, some also escape ' and \n, \r, \t depending on context,
#         # but &quot; is the primary one for values in double quotes.
#         # text_str = text_str.replace("'", "&apos;") # &apos; is valid but less universally supported
#
#     return text_str


def smart_escape_preserving_embedded(text, is_attribute=False):
    # No .strip() here initially, let re.split handle segments
    text_str = str(text)

    if not KNOWN_ENTITY_NAMES:
        # Fallback: If no known entities, apply basic full escaping
        # This also implicitly handles cases where KNOWN_ENTITY_NAMES might be None if populate wasn't called (defensive)
        escaped_text = text_str.replace("&", "&amp;")
        escaped_text = escaped_text.replace("<", "&lt;")
        escaped_text = escaped_text.replace(">", "&gt;")
        if is_attribute:
            escaped_text = escaped_text.replace("\"", "&quot;")
        return escaped_text

    # Sort by length descending to match longest possible entity first (e.g., &longname; before &long;)
    # This is crucial for correctness if some entity names are substrings of others.
    sorted_entity_names = sorted(KNOWN_ENTITY_NAMES, key=len, reverse=True)

    # Create a regex pattern to find any of our known entities.
    # The pattern should capture the full entity reference, e.g., (&(entity1|entity2);)
    # This ensures that re.split() includes the delimiters (the entities themselves) in the result.
    # Make sure entity names are re.escaped if they could contain regex special characters (unlikely for typical entity names).
    # For this use case, entity names are from YAML keys, typically simple strings.
    entity_names_pattern_part = "|".join(
        [re.escape(name) for name in sorted_entity_names])

    # If entity_names_pattern_part is empty (e.g. KNOWN_ENTITY_NAMES was empty but not None),
    # also fallback to full escaping to avoid re.compile error with empty pattern part.
    if not entity_names_pattern_part:
        # Same fallback as `if not KNOWN_ENTITY_NAMES:`
        escaped_text = text_str.replace("&", "&amp;")
        escaped_text = escaped_text.replace("<", "&lt;")
        escaped_text = escaped_text.replace(">", "&gt;")
        if is_attribute:
            escaped_text = escaped_text.replace("\"", "&quot;")
        return escaped_text

    # Regex to find known entities: &name1; or &name2; etc.
    # We capture only the name part to verify against KNOWN_ENTITY_NAMES, but use group(0) for the full entity.
    entity_regex = re.compile(f"&({entity_names_pattern_part});")

    processed_parts = []
    last_end = 0
    for match in entity_regex.finditer(text_str):
        start, end = match.span()
        # entity_name_matched = match.group(1) # The captured name (e.g., "author")
        # Not strictly needed if we just use match.group(0)

        # Append the text segment before this match, duly escaped
        non_entity_segment = text_str[last_end:start]
        # Basic escaping for non-entity segments
        escaped_segment = non_entity_segment.replace("&", "&amp;")
        escaped_segment = escaped_segment.replace("<", "&lt;")
        escaped_segment = escaped_segment.replace(">", "&gt;")
        if is_attribute:
            escaped_segment = escaped_segment.replace("\"", "&quot;")
        processed_parts.append(escaped_segment)

        # Append the full entity reference itself (e.g., "&author;")
        # group(0) is the full match e.g. &author;
        processed_parts.append(match.group(0))

        last_end = end

    # Append the remaining part of the string after the last match, duly escaped
    remaining_segment = text_str[last_end:]
    escaped_remaining_segment = remaining_segment.replace("&", "&amp;")
    escaped_remaining_segment = escaped_remaining_segment.replace("<", "&lt;")
    escaped_remaining_segment = escaped_remaining_segment.replace(">", "&gt;")
    if is_attribute:
        escaped_remaining_segment = escaped_remaining_segment.replace(
            "\"", "&quot;")
    processed_parts.append(escaped_remaining_segment)

    return "".join(processed_parts)


def generate_dtd_entities(entities_dict):
    """
    Generates DTD entity strings from a dictionary.
    Pads keys for visual alignment.
    """
    if not entities_dict:
        return []

    max_key_length = 0
    if entities_dict:  # Ensure entities_dict is not empty before finding max length
        # Ensure all keys are strings before calling len()
        str_keys = [str(key) for key in entities_dict.keys()]
        if str_keys:
            max_key_length = max(len(key) for key in str_keys)

    dtd_entity_strings = []
    for key, value in entities_dict.items():
        value_str = str(value).replace('"', '&quot;')
        # Ensure key is string for padding calculation
        padding = " " * (max_key_length - len(str(key)))
        dtd_entity_strings.append(
            f'<!ENTITY {str(key)}{padding} "{value_str}">')
    return dtd_entity_strings


def main():
    try:
        yaml_file_path = "test.yaml"
        entities_dict = {}  # Initialize to ensure it's always a dict
        data = None

        yaml_parser = YAML(typ='rt')
        try:
            with open(yaml_file_path, 'r') as f:
                data = yaml_parser.load(f)

            if data and "ENTITIES" in data and isinstance(data["ENTITIES"], dict):
                entities_dict = data["ENTITIES"]
            elif data and "ENTITIES" in data:  # Exists but not a dict
                print(
                    f"Error: 'ENTITIES' key in {yaml_file_path} is not a dictionary.", file=sys.stderr)
                # entities_dict remains {}
            elif data:  # Data loaded but ENTITIES key missing
                print(
                    f"Error: 'ENTITIES' key not found in {yaml_file_path}.", file=sys.stderr)
                # entities_dict remains {}
            else:  # Data could not be loaded or is empty
                print(
                    f"Error: No data loaded from {yaml_file_path} or data is empty.", file=sys.stderr)
                return  # Critical error, cannot proceed

        except FileNotFoundError:
            print(
                f"Error: YAML file not found at {yaml_file_path}", file=sys.stderr)
            return
        except Exception as e:
            print(
                f"Error parsing YAML file '{yaml_file_path}': {e}", file=sys.stderr)
            return

        # Populate the global list of known entity names
        populate_known_entities(entities_dict)

        # Generate and print DTD Entities
        dtd_entities = generate_dtd_entities(entities_dict)
        print("<!DOCTYPE PLUGIN [")
        for entity_str in dtd_entities:
            print(f"  {entity_str}")
        print("]>\n")

        # Generate and print <PLUGIN> tag
        plugin_attributes = []
        for key, value in entities_dict.items():  # Iterate through key-value pairs
            attr_name = str(key)
            # Get the raw value from entities_dict. smart_escape_preserving_embedded will convert to str.
            escaped_value = smart_escape_preserving_embedded(
                value, is_attribute=True)
            plugin_attributes.append(f'{attr_name}="{escaped_value}"')

        # Ensure there's a space after <PLUGIN if there are attributes
        if plugin_attributes:
            plugin_tag_str = "<PLUGIN " + \
                " ".join(plugin_attributes) + ">"  # Removed \n
        else:
            plugin_tag_str = "<PLUGIN>"
        print(plugin_tag_str)

        # Process <CHANGES> block
        if data and "CHANGES" in data:
            changes_file_path = data["CHANGES"]
            if isinstance(changes_file_path, str):
                try:
                    with open(changes_file_path, 'r') as f_changes:
                        changes_content = f_changes.read()
                    print("<CHANGES>")
                    # Removed end='', let print add newline
                    print(changes_content)
                    print("</CHANGES>")   # Removed \n from string
                except FileNotFoundError:
                    print(
                        f"Error: Changes file '{changes_file_path}' specified in 'CHANGES' key not found.", file=sys.stderr)
                except Exception as e:
                    print(
                        f"Error reading changes file '{changes_file_path}': {e}", file=sys.stderr)
            else:
                print(
                    f"Error: Value of 'CHANGES' key must be a string (filepath), but found {type(changes_file_path)}.", file=sys.stderr)

        # Process FILE list
        if data and "FILE" in data and isinstance(data["FILE"], list):
            file_list = data["FILE"]  # This is a CommentedSeq
            for item_idx, file_item in enumerate(file_list):
                # In ruamel.yaml, dicts are CommentedMap
                if not isinstance(file_item, dict):
                    print(
                        f"Warning: Item in FILE list is not a dictionary: {file_item}", file=sys.stderr)
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
                            raw_comment_text = "".join(
                                [ct.value for ct in comment_tokens]).strip()
                            if raw_comment_text.startswith("#"):
                                comment_text = raw_comment_text[1:].strip()
                                comment_str = f"<!-- {comment_text} -->"

                if comment_str:
                    print(comment_str)

                attributes = []
                # Skip if file_item is empty (e.g. a list item that's just a comment placeholder)
                # ensure it's not just a comment
                if not file_item and not (item_idx in file_list.ca.items and file_list.ca.items[item_idx][1]):
                    # If file_item is empty AND it doesn't have an associated comment, then skip.
                    # If it has a comment, it will be printed, and then we'd print an empty <FILE /> if we don't continue.
                    # The goal is to not print <FILE /> for truly empty items.
                    # A file_item that is just a comment in YAML (e.g. '- # Just a comment line') results in an empty file_item (None).
                    # In ruamel.yaml, an empty item in a sequence that only had a comment might result in file_item being None.
                    # The check `if not isinstance(file_item, dict)` handles `None` items.
                    # If file_item is an empty dict `{}`, it will not be skipped by `isinstance`.
                    if not file_item:  # file_item is an empty dict {}
                        if not comment_str:  # And no comment was printed for it
                            continue  # Skip printing <FILE /> for a truly empty item {} that had no comment
                        # If there was a comment, an empty <FILE /> might be desired by some. For now, let's print it.

                attribute_strings = []
                generic_child_tag_strings = []  # Renamed from child_tag_strings
                inline_key_info = None
                cdata_key_info = None
                key_order_counter = 0

                for key, value in file_item.items():  # Single loop for keys
                    key_order_counter += 1
                    key_str = str(key)

                    if key_str == 'INLINE':
                        inline_key_info = {'path': str(
                            value), 'order': key_order_counter}
                        # INLINE content processing is deferred
                    elif key_str == 'CDATA':
                        cdata_key_info = {'path': str(
                            value), 'order': key_order_counter}
                        # CDATA content processing is deferred
                    elif key_str.startswith('@'):
                        attr_name = key_str[1:]
                        attribute_strings.append(
                            f'{attr_name}="{smart_escape_preserving_embedded(value, is_attribute=True)}"')
                    else:
                        # This key is for a generic child tag (URL, MD5, SpecialTag, etc.)
                        tag_name = key_str
                        escaped_content = smart_escape_preserving_embedded(
                            value, is_attribute=False)
                        generic_child_tag_strings.append(f"<{tag_name}>")
                        generic_child_tag_strings.append(escaped_content)
                        generic_child_tag_strings.append(f"</{tag_name}>")

                # --- INLINE/CDATA Decision Logic ---
            # final_inline_tag_string = None # No longer needed

                file_item_identifier = f"item at index {item_idx}"
                # Try to get @Name for better identifier in warnings
                # attribute_strings is like ['Name="val"', 'Mode="val"']
                for attr_str in attribute_strings:
                    if attr_str.startswith('Name="'):
                        # Extract value from Name="value"
                        # Remove Name=" and trailing "
                        name_val = attr_str[len('Name="'):-1]
                        file_item_identifier = f"FILE item with @Name='{name_val}'"
                        break

                if inline_key_info and cdata_key_info:
                    print(
                        f"Warning: {file_item_identifier} has both INLINE and CDATA keys. Using the one that appears last in the YAML.", file=sys.stderr)
                    if cdata_key_info['order'] > inline_key_info['order']:
                        # CDATA is last, use CDATA
                        try:
                            with open(cdata_key_info['path'], 'r') as f_cdata:
                                raw_content = f_cdata.read()
                        generic_child_tag_strings.append("<INLINE>")
                        generic_child_tag_strings.append(
                            f"<![CDATA[{raw_content}]]>")
                        generic_child_tag_strings.append("</INLINE>")
                        except FileNotFoundError:
                            raw_content = f"<!-- Error: CDATA file not found: {smart_escape_preserving_embedded(cdata_key_info['path'], is_attribute=False)} -->"
                        generic_child_tag_strings.append("<INLINE>")
                        generic_child_tag_strings.append(raw_content)
                        generic_child_tag_strings.append("</INLINE>")
                        except Exception as e:
                            raw_content = f"<!-- Error reading CDATA file {smart_escape_preserving_embedded(cdata_key_info['path'], is_attribute=False)}: {smart_escape_preserving_embedded(str(e), is_attribute=False)} -->"
                        generic_child_tag_strings.append("<INLINE>")
                        generic_child_tag_strings.append(raw_content)
                        generic_child_tag_strings.append("</INLINE>")
                    else:
                        # INLINE is last (or same order, implies INLINE first if stable sort, or as per dict order), use INLINE
                        try:
                            with open(inline_key_info['path'], 'r') as f_inline:
                                raw_content = f_inline.read()
                        generic_child_tag_strings.append("<INLINE>")
                        generic_child_tag_strings.append(
                            std_escape(raw_content))
                        generic_child_tag_strings.append("</INLINE>")
                        except FileNotFoundError:
                            raw_content = f"<!-- Error: INLINE file not found: {smart_escape_preserving_embedded(inline_key_info['path'], is_attribute=False)} -->"
                        generic_child_tag_strings.append("<INLINE>")
                        generic_child_tag_strings.append(raw_content)
                        generic_child_tag_strings.append("</INLINE>")
                        except Exception as e:
                            raw_content = f"<!-- Error reading INLINE file {smart_escape_preserving_embedded(inline_key_info['path'], is_attribute=False)}: {smart_escape_preserving_embedded(str(e), is_attribute=False)} -->"
                        generic_child_tag_strings.append("<INLINE>")
                        generic_child_tag_strings.append(raw_content)
                        generic_child_tag_strings.append("</INLINE>")

                elif cdata_key_info:
                    # Only CDATA found
                    try:
                        with open(cdata_key_info['path'], 'r') as f_cdata:
                            raw_content = f_cdata.read()
                    generic_child_tag_strings.append("<INLINE>")
                    generic_child_tag_strings.append(
                        f"<![CDATA[{raw_content}]]>")
                    generic_child_tag_strings.append("</INLINE>")
                    except FileNotFoundError:
                        raw_content = f"<!-- Error: CDATA file not found: {smart_escape_preserving_embedded(cdata_key_info['path'], is_attribute=False)} -->"
                    generic_child_tag_strings.append("<INLINE>")
                    generic_child_tag_strings.append(raw_content)
                    generic_child_tag_strings.append("</INLINE>")
                    except Exception as e:
                        raw_content = f"<!-- Error reading CDATA file {smart_escape_preserving_embedded(cdata_key_info['path'], is_attribute=False)}: {smart_escape_preserving_embedded(str(e), is_attribute=False)} -->"
                    generic_child_tag_strings.append("<INLINE>")
                    generic_child_tag_strings.append(raw_content)
                    generic_child_tag_strings.append("</INLINE>")

                elif inline_key_info:
                    # Only INLINE found
                    try:
                        with open(inline_key_info['path'], 'r') as f_inline:
                            raw_content = f_inline.read()
                    generic_child_tag_strings.append("<INLINE>")
                    generic_child_tag_strings.append(std_escape(raw_content))
                    generic_child_tag_strings.append("</INLINE>")
                    except FileNotFoundError:
                        raw_content = f"<!-- Error: INLINE file not found: {smart_escape_preserving_embedded(inline_key_info['path'], is_attribute=False)} -->"
                    generic_child_tag_strings.append("<INLINE>")
                    generic_child_tag_strings.append(raw_content)
                    generic_child_tag_strings.append("</INLINE>")
                    except Exception as e:
                        raw_content = f"<!-- Error reading INLINE file {smart_escape_preserving_embedded(inline_key_info['path'], is_attribute=False)}: {smart_escape_preserving_embedded(str(e), is_attribute=False)} -->"
                    generic_child_tag_strings.append("<INLINE>")
                    generic_child_tag_strings.append(raw_content)
                    generic_child_tag_strings.append("</INLINE>")

                # Construct and print the <FILE> tag
            # Construct <FILE ...> start tag
            file_start_tag = "<FILE"
            if attribute_strings:
                file_start_tag += " " + " ".join(attribute_strings)

            if not generic_child_tag_strings:
                # attribute_strings or file_item check was to prevent empty <FILE /> for items that were only comments.
                # This should be implicitly handled by the earlier `continue` for such items.
                # If file_item is an empty dict {} it should print <FILE />.
                print(file_start_tag + " />")
            else:  # Has child tags
                print(file_start_tag + ">")  # Opening <FILE ...> tag

                # Print children (generic tags, INLINE content)
                for child_part in generic_child_tag_strings:
                    print(child_part)

                print("</FILE>")  # Closing </FILE> tag

        elif data and "FILE" in data:  # FILE key exists but is not a list
            print(
                f"Error: 'FILE' key in {yaml_file_path} exists but is not a list.", file=sys.stderr)
    finally:
        print("</PLUGIN>")


if __name__ == "__main__":
    main()
