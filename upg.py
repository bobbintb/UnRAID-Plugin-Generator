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
import os
import subprocess
import tempfile
import stat
import argparse
import json


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


def calculate_md5_from_file(filepath):
    """Calculate MD5 hash from a local file."""
    try:
        md5_hash = hashlib.md5()
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except Exception as e:
        print(f"Error reading file: {e}")
        return None


def create_slackware_package(source_path, output_dir=None):
    """
    Create a Slackware package from a directory structure.
    
    Args:
        source_path: Path to directory containing package structure
        output_dir: Directory to place output package (default: source_path parent)
    
    Returns:
        Path to created package file, or None on error
    """
    source_path = Path(source_path).resolve()
    if not source_path.exists():
        print(f"Error: Source path does not exist: {source_path}")
        return None
    
    if not source_path.is_dir():
        print(f"Error: Source path is not a directory: {source_path}")
        return None
    
    # Determine output directory
    if output_dir is None:
        output_dir = source_path.parent
    else:
        output_dir = Path(output_dir).resolve()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if makepkg already exists in script directory
    script_dir = Path(__file__).parent if '__file__' in globals() else Path.cwd()
    makepkg_path = script_dir / 'makepkg'
    
    if makepkg_path.exists():
        print(f"Using existing makepkg from {makepkg_path}")
    else:
        # Download makepkg script
        makepkg_url = "https://mirrors.slackware.com/slackware/slackware64-15.0/source/a/pkgtools/scripts/makepkg"
        
        print(f"Downloading makepkg from {makepkg_url}...")
        try:
            with urllib.request.urlopen(makepkg_url) as response:
                makepkg_path.write_bytes(response.read())
            print(f"Downloaded makepkg to {makepkg_path}")
        except Exception as e:
            print(f"Error downloading makepkg: {e}")
            return None
    
    # Make makepkg executable
    os.chmod(makepkg_path, os.stat(makepkg_path).st_mode | stat.S_IEXEC)
    
    try:
        # makepkg must be run from inside the package directory
        # The package will be created in the parent directory
        package_name = f'{source_path.name}.txz'
        print(f"Creating Slackware package from {source_path}...")
        print(f"Running: {makepkg_path} -l y -c n ../{package_name}")
        print(f"Working directory: {source_path}")
        
        result = subprocess.run(
            [makepkg_path, '-l', 'y', '-c', 'n', f'../{package_name}'],
            cwd=source_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Error running makepkg (exit code {result.returncode}):")
            if result.stdout:
                print("STDOUT:", result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
            return None
        
        print("makepkg output:", result.stdout)
        
        # Package is created in parent directory
        package_file = source_path.parent / package_name
        
        if package_file.exists():
            # Move to output directory if different
            final_path = output_dir / package_file.name
            if package_file != final_path:
                package_file.rename(final_path)
                package_file = final_path
            
            print(f"Package created: {package_file}")
            return package_file
        else:
            print("Error: Package file was not created")
            print(f"Expected package at: {package_file}")
            return None
            
    except Exception as e:
        print(f"Error creating package: {e}")
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





def main():
    parser = argparse.ArgumentParser(
        description='Convert TOML configuration to UnRAID plugin XML format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Use TOML file
  python toml_to_xml.py config.toml -o output.plg
  
  # Override specific entities
  python toml_to_xml.py config.toml -o output.plg --entity version=2025.12.23.1500
  
  # Create from scratch with arguments
  python toml_to_xml.py --entity name=my.plugin --entity author=me --changes README.md -o output.plg
  
  # Add FILE entries
  python toml_to_xml.py config.toml --file '{"Attr": {"Run": "/bin/bash"}, "INLINE": "./script.sh"}'
        '''
    )
    
    parser.add_argument('toml_file', nargs='?', help='Input TOML configuration file (optional if using --entity and --file)')
    parser.add_argument('-o', '--output', help='Output XML plugin file (prints to stdout if omitted)')
    parser.add_argument('-b', '--base-path', default='.', help='Base path for resolving relative file paths (default: .)')
    parser.add_argument('-p', '--package-source', help='Path to directory to create Slackware package from')
    parser.add_argument('--entity', action='append', metavar='KEY=VALUE', help='Add or override an entity (can be used multiple times)')
    parser.add_argument('--changes', help='Path to changes/changelog file')
    parser.add_argument('--file', action='append', metavar='JSON', help='Add a FILE entry as JSON (can be used multiple times)')
    
    args = parser.parse_args()
    
    # Initialize config
    entities = {}
    changes = {}
    files = []
    
    # Load TOML file if provided
    if args.toml_file:
        if not Path(args.toml_file).exists():
            print(f"Error: TOML file not found: {args.toml_file}")
            sys.exit(1)
        
        toml_content = Path(args.toml_file).read_text()
        doc = tomlkit.parse(toml_content)
        
        entities = dict(doc.get('ENTITIES', {}))
        changes = dict(doc.get('CHANGES', {}))
        files = list(doc.get('FILE', []))
        
        # Extract comments from TOML
        comment_map, toml_lines = extract_comments_map(toml_content)
        file_lines = [i for i, line in enumerate(toml_lines) if line.strip() == '[[FILE]]']
    else:
        comment_map = {}
        file_lines = []
    
    # Override/add entities from command line
    if args.entity:
        for entity_arg in args.entity:
            if '=' not in entity_arg:
                print(f"Error: Invalid entity format '{entity_arg}'. Use KEY=VALUE")
                sys.exit(1)
            key, value = entity_arg.split('=', 1)
            entities[key.strip()] = value.strip()
    
    # Override changes from command line
    if args.changes:
        changes['File'] = args.changes
    
    # Add FILE entries from command line
    if args.file:
        for file_arg in args.file:
            try:
                file_data = json.loads(file_arg)
                files.append(file_data)
                file_lines.append(None)  # No line number for CLI files
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON in --file argument: {e}")
                sys.exit(1)
    
    # Check if we have enough to generate a plugin
    if not entities and not files:
        parser.print_help()
        sys.exit(1)
    
    # Create Slackware package if source path provided
    package_file = None
    if args.package_source:
        output_dir = Path(args.base_path) if args.base_path != "." else Path.cwd()
        package_file = create_slackware_package(args.package_source, output_dir)
        if not package_file:
            print("Warning: Failed to create Slackware package")
    
    # Auto-generate version if not present
    if 'version' not in entities:
        now = datetime.now()
        version = f"{now.year}.{now.month:02d}.{now.day:02d}.{now.hour:02d}{now.minute:02d}"
        entities['version'] = version
        print(f"Auto-generated version: {version}")
    
    # Auto-generate MD5 if not present
    if 'MD5' not in entities:
        md5 = None
        
        # Try to use the created package file first
        if package_file:
            print(f"Calculating MD5 from created package: {package_file}")
            md5 = calculate_md5_from_file(package_file)
        # Otherwise try to download from packageURL
        elif 'packageURL' in entities:
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
        changes_path = Path(args.base_path) / changes['File']
        changes_content = read_file_content(changes_path)
        xml_lines.append(changes_content)
    xml_lines.append('</CHANGES>')
    xml_lines.append("")
    
    # FILE elements with comments
    for i, file_data in enumerate(files):
        # Get comments for this FILE entry (only from TOML)
        if i < len(file_lines) and file_lines[i] is not None and file_lines[i] in comment_map:
            comments = comment_map[file_lines[i]]
            if comments:
                comment_text = '\n'.join(comments)
                xml_lines.append(f'<!-- {comment_text} -->')
        
        xml_lines.append(build_file_element(file_data, args.base_path))
        xml_lines.append("")
    
    # PLUGIN closing tag
    xml_lines.append('</PLUGIN>')
    
    # Join and return
    xml_output = '\n'.join(xml_lines)
    
    # Write to file if output path specified
    if args.output:
        Path(args.output).write_text(xml_output)
        print(f"XML written to: {args.output}")
    else:
        print(xml_output)


if __name__ == '__main__':
    main()
