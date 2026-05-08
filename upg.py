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


def calculate_md5(source):
    """
    Calculate MD5 hash from either a URL or a local file path.
    """
    is_url = str(source).startswith(('http://', 'https://', 'ftp://'))

    try:
        if is_url:
            print(f"Downloading {source} to calculate MD5...")
            cm = urllib.request.urlopen(source)
        else:
            print(f"Reading local file {source} to calculate MD5...")
            cm = open(source, 'rb')

        with cm as f:
            md5_hash = hashlib.md5()
            while chunk := f.read(8192):
                md5_hash.update(chunk)
            return md5_hash.hexdigest()

    except Exception as e:
        print(f"Error calculating MD5 for {source}: {e}")
        return None


def resolve_package_source(package_source):
    """
    Resolve package_source to a local directory path.

    If package_source looks like a URL, verify it is a git repository, clone it
    into a temporary directory, and return that path.  If it is a local path,
    return it unchanged.

    Returns:
        (resolved_path, tmpdir)
          - resolved_path: Path object, or None on failure.
          - tmpdir: TemporaryDirectory object that must be kept alive by the
                    caller for as long as resolved_path is needed, or None when
                    the source is already a local directory.
    """
    is_url = package_source.startswith(
        ('http://', 'https://', 'git://', 'git@', 'ssh://')
    )

    if not is_url:
        return Path(package_source), None

    url = package_source
    print(f"Detected URL: {url}")

    # Verify it's a git repo before cloning
    print(f"Verifying git repository at {url}...")
    result = subprocess.run(
        ['git', 'ls-remote', '--exit-code', url],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Error: URL does not appear to be a valid git repository: {url}")
        if result.stderr.strip():
            print(result.stderr.strip())
        return None, None

    # Clone into a managed temporary directory
    tmpdir = tempfile.TemporaryDirectory()
    clone_path = Path(tmpdir.name) / 'repo'
    print(f"Cloning {url} into {clone_path}...")
    result = subprocess.run(
        ['git', 'clone', url, str(clone_path)],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Error cloning repository:")
        print(result.stderr.strip())
        tmpdir.cleanup()
        return None, None

    print(f"Repository cloned to: {clone_path}")
    return clone_path, tmpdir


def create_slackware_package(source_path, output_dir=None):
    """
    Create a Slackware package from a directory structure with full debug output.
    """
    source_path = Path(source_path).resolve()
    if not source_path.exists():
        print(f"Error: Source path does not exist: {source_path}")
        return None

    if not source_path.is_dir():
        print(f"Error: Source path is not a directory: {source_path}")
        return None

    if output_dir is None:
        output_dir = source_path.parent
    else:
        output_dir = Path(output_dir).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    makepkg_url = "https://mirrors.slackware.com/slackware/slackware64-15.0/source/a/pkgtools/scripts/makepkg"

    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='_makepkg') as tmp:
        makepkg_path = tmp.name
        try:
            print(f"Downloading makepkg from {makepkg_url}...")
            with urllib.request.urlopen(makepkg_url) as response:
                tmp.write(response.read())
        except Exception as e:
            print(f"Error downloading makepkg: {e}")
            return None

    os.chmod(makepkg_path, os.stat(makepkg_path).st_mode | stat.S_IEXEC)

    try:
        # We use a clean filename for the package to avoid issues with parent dir names
        pkg_name = f"{source_path.name}.txz"
        print(f"Creating Slackware package from {source_path}...")
        
        # Capture BOTH stdout and stderr to catch the real reason for failure
        result = subprocess.run(
            [makepkg_path, '-l', 'y', '-c', 'n', pkg_name],
            cwd=source_path,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print("--- MAKEPKG ERROR LOG START ---")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            print("--- MAKEPKG ERROR LOG END ---")
            return None

        package_file = source_path / pkg_name

        if package_file.exists():
            final_path = output_dir / package_file.name
            if package_file != final_path:
                # Use shutil for more robust moving across filesystems
                import shutil
                shutil.move(str(package_file), str(final_path))
                package_file = final_path

            print(f"Package created successfully: {package_file}")
            return package_file
        else:
            print(f"Error: makepkg exited 0 but {pkg_name} was not found.")
            return None

    finally:
        if os.path.exists(makepkg_path):
            os.unlink(makepkg_path)


def read_file_content(filepath):
    """Read content from a file path."""
    path = Path(filepath)
    if not path.exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)
    return path.read_text()


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
        if key.upper() == 'SCRIPT_TEMPLATE':
            inline_key = key
        elif key.upper() == 'SCRIPT_RAW':
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
  
  # Entities:
  name (required)
  author (required)
  repo = (required)
  tag (optional)
  launch = "Settings/Deduplication in Real-Time"
  pluginURL (required)
  packageURL (required)
  source = (optional - defaults to `/boot/config/plugins/&name;/&name;`, which is standard for Unraid)
  icon = "fa-search-minus"
  min (optional - Unraid will not install the plugin if the Unraid version is lower than this)
  max (optional - Unraid will not install the plugin if the Unraid version is higher than this)
  version (optional - automatically generated if not supplied)
  MD5 (optional - automatically generated if not supplied)
        '''
    )

    parser.add_argument('toml_file', nargs='?',
                        help='Input TOML configuration file (optional if using --entity and --file)')
    parser.add_argument('-o', '--output', help='Output XML plugin file (prints to stdout if omitted)')
    parser.add_argument('-b', '--base-path', default='.',
                        help='Base path for resolving relative file paths (default: .)')
    parser.add_argument('-p', '--package-source', help='Path to directory to create Slackware package from')
    parser.add_argument('--entity', action='append', metavar='KEY=VALUE',
                        help='Add or override an entity (can be used multiple times)')
    parser.add_argument('--changes', help='Path to changes/changelog file')
    parser.add_argument('--file', action='append', metavar='JSON',
                        help='Add a FILE entry as JSON (can be used multiple times)')

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
        # Resolve to a local directory, cloning first if a URL was given.
        # _tmpdir must stay in scope until we're done with the cloned directory.
        package_source_path, _tmpdir = resolve_package_source(args.package_source)
        if package_source_path is None:
            print("Error: Could not resolve --package-source to a local directory.")
            sys.exit(1)

        output_dir = Path(args.base_path) if args.base_path != "." else Path.cwd()
        package_file = create_slackware_package(package_source_path, output_dir)
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
        source_to_hash = None

    if package_file:
        source_to_hash = package_file
    elif 'packageURL' in entities:
        # Expand entity references in packageURL
        package_url = entities['packageURL']
        for key, value in entities.items():
            package_url = package_url.replace(f'&{key};', value)
        source_to_hash = package_url

    if source_to_hash:
        md5 = calculate_md5(source_to_hash)
        if md5:
            entities['MD5'] = md5
            print(f"Auto-generated MD5: {md5}")
        else:
            print("Warning: No source available to generate MD5 hash")

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
