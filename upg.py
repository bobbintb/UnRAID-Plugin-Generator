#!/usr/bin/env python3
"""
Convert TOML configuration to UnRAID plugin XML format.
Requires: tomlkit (pip install tomlkit)

Usage:
    python toml_to_xml.py input.toml output.plg
"""

import tomlkit
import sys
from pathlib import Path
from datetime import datetime
import hashlib
import urllib.request


def calculate_md5_from_url(url):
    """Download a file from URL and calculate its MD5 hash."""
    try:
        print(f"Downloading {url} to calculate MD5...")
        with urllib.request.urlopen(url) as response:
            md5_hash = hashlib.md5()
            while chunk := response.read(8192):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except Exception as e:
        print(f"Error downloading file: {e}")
        return None


def read_file_content(filepath):
    """Read content from a file path."""
    path = Path(filepath)
    if path.exists():
        return path.read_text()
    return f"<!-- File not found: {filepath} -->"


def extract_comments_map(toml_text):
    """
    Extract all comments and associate them with the next non-comment line.
    Returns dict mapping line_number -> list of comment lines before it.
    """
    lines = toml_text.split('\n')
    comment_map = {}
    accumulated_comments = []
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        if stripped.startswith('#'):
            # This is a comment line
            accumulated_comments.append(stripped.lstrip('#').strip())
        elif stripped:
            # Non-empty, non-comment line - attach accumulated comments
            if accumulated_comments:
                comment_map[i] = accumulated_comments.copy()
                accumulated_comments = []
        # Empty lines don't reset comments
    
    return comment_map, lines


def build_dtd(entities):
    """Build the DTD section from entities."""
    lines = ["<!DOCTYPE PLUGIN ["]
    for key, value in entities.items():
        lines.append(f'<!ENTITY {key:<12} "{value}">')
    lines.append("]>")
    return '\n'.join(lines)


def build_plugin_attrs(entities):
    """Build PLUGIN element attributes from entities."""
    attrs = []
    for key in entities.keys():
        attrs.append(f'{key}="&{key};"')
    
    return ' '.join(attrs)


def build_file_element(file_data, base_path="."):
    """Build a FILE element from TOML data."""
    lines = []
    
    # Build opening tag with attributes
    attrs = []
    if 'Attr' in file_data:
        for key, value in file_data['Attr'].items():
            attrs.append(f'{key}="{value}"')
    
    if attrs:
        lines.append(f'<FILE {" ".join(attrs)}>')
    else:
        lines.append('<FILE>')
    
    # Add INLINE content if specified (case-insensitive check)
    inline_key = None
    cdata_key = None
    
    for key in file_data.keys():
        if key.upper() == 'INLINE':
            inline_key = key
        elif key.upper() == 'CDATA':
            cdata_key = key
    
    if inline_key or cdata_key:
        lines.append('<INLINE>')
        
        if cdata_key:
            # CDATA wrapped in INLINE
            cdata_path = Path(base_path) / file_data[cdata_key]
            content = read_file_content(cdata_path)
            lines.append('<![CDATA[')
            lines.append(content)
            lines.append(']]>')
        elif inline_key:
            # Regular INLINE content
            inline_path = Path(base_path) / file_data[inline_key]
            content = read_file_content(inline_path)
            lines.append(content)
        
        lines.append('</INLINE>')
    
    # Add URL if specified
    if 'URL' in file_data:
        lines.append(f'<URL>{file_data["URL"]}</URL>')
    
    # Add MD5 if specified
    if 'MD5' in file_data:
        lines.append(f'<MD5>{file_data["MD5"]}</MD5>')
    
    lines.append('</FILE>')
    return '\n'.join(lines)


def toml_to_plugin_xml(toml_path, output_path=None, base_path="."):
    """
    Convert TOML file to UnRAID plugin XML format.
    
    Args:
        toml_path: Path to input TOML file
        output_path: Path to output XML file (optional)
        base_path: Base path for resolving relative file paths in TOML
    """
    # Read raw TOML content
    toml_content = Path(toml_path).read_text()
    
    # Parse TOML
    doc = tomlkit.parse(toml_content)
    
    # Extract comments
    comment_map, toml_lines = extract_comments_map(toml_content)
    
    # Find line numbers for [[FILE]] entries
    file_lines = []
    for i, line in enumerate(toml_lines):
        if line.strip() == '[[FILE]]':
            file_lines.append(i)
    
    # Extract sections
    entities = doc.get('ENTITIES', {})
    changes = doc.get('CHANGES', {})
    files = doc.get('FILE', [])
    
    # Auto-generate version if not present
    if 'version' not in entities:
        now = datetime.now()
        version = f"{now.year}.{now.month:02d}.{now.day:02d}.{now.hour:02d}{now.minute:02d}"
        entities['version'] = version
        print(f"Auto-generated version: {version}")
    
    # Auto-generate MD5 if not present
    if 'MD5' not in entities and 'packageURL' in entities:
        # Expand entity references in packageURL
        package_url = entities['packageURL']
        for key, value in entities.items():
            package_url = package_url.replace(f'&{key};', value)
        
        md5 = calculate_md5_from_url(package_url)
        if md5:
            entities['MD5'] = md5
            print(f"Auto-generated MD5: {md5}")
        else:
            print("Warning: Failed to generate MD5 hash")
    
    # Build XML
    xml_lines = []
    
    # XML declaration
    xml_lines.append("<?xml version='1.0' standalone='yes'?>")
    xml_lines.append("")
    
    # DTD
    xml_lines.append(build_dtd(entities))
    xml_lines.append("")
    
    # PLUGIN opening tag
    plugin_attrs = build_plugin_attrs(entities)
    xml_lines.append(f'<PLUGIN {plugin_attrs}>')
    xml_lines.append("")
    
    # CHANGES section
    xml_lines.append('<CHANGES>')
    if 'File' in changes:
        changes_path = Path(base_path) / changes['File']
        changes_content = read_file_content(changes_path)
        xml_lines.append(changes_content)
    xml_lines.append('</CHANGES>')
    xml_lines.append("")
    
    # FILE elements with comments
    for i, file_data in enumerate(files):
        # Get comments for this FILE entry
        if i < len(file_lines) and file_lines[i] in comment_map:
            comments = comment_map[file_lines[i]]
            if comments:
                # Join with newlines to preserve multi-line comments
                comment_text = '\n'.join(comments)
                xml_lines.append(f'<!-- {comment_text} -->')
        
        xml_lines.append(build_file_element(file_data, base_path))
        xml_lines.append("")
    
    # PLUGIN closing tag
    xml_lines.append('</PLUGIN>')
    
    # Join and return
    xml_output = '\n'.join(xml_lines)
    
    # Write to file if output path specified
    if output_path:
        Path(output_path).write_text(xml_output)
        print(f"XML written to: {output_path}")
    
    return xml_output


def main():
    if len(sys.argv) < 2:
        print("Usage: python toml_to_xml.py input.toml [output.plg] [base_path]")
        print("  input.toml  - Input TOML configuration file")
        print("  output.plg  - Output XML plugin file (optional, prints to stdout if omitted)")
        print("  base_path   - Base path for resolving relative file paths (default: .)")
        sys.exit(1)
    
    toml_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    base_path = sys.argv[3] if len(sys.argv) > 3 else "."
    
    if not Path(toml_path).exists():
        print(f"Error: TOML file not found: {toml_path}")
        sys.exit(1)
    
    xml_output = toml_to_plugin_xml(toml_path, output_path, base_path)
    
    if not output_path:
        print(xml_output)


if __name__ == '__main__':
    main()
