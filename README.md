# UnRAID Plugin Generator

Plugin files in Unraid are just XML files but they can be difficult to manage. This script addresses that by creating a `*.plg` file for Unraid from a TOML configuration file and other source files. A sample TOML file is included for reference.

## Requirements

```bash
pip install tomlkit
```

## Example TOML Configuration

```toml
[ENTITIES]
name = "bobbintb.system.dirt"
author = "bobbintb"
repo = "UnRAID-DiRT"
tag = "test"
launch = "Settings/Deduplication in Real-Time"
pluginURL = "https://github.com/&author;/&repo;/releases/download/&tag;/&name;.plg"
packageURL = "https://github.com/&author;/&repo;/releases/download/&tag;/&name;.txz"
source = "/boot/config/plugins/&name;/&name;"
icon = "fa-search-minus"
min = "6.1.9"
version = "2025.02.11"
MD5 = "b31ca4f4cc86325d132739c93f79b922"

[CHANGES]
File = "./README.md"

# --- FILES ---

# 1. Startup Script
[[FILE]]
Attr = { Name = "/etc/rc.d/rc.dirt", Mode = "0775" }
INLINE = "./.plugin/rc.dirt"

# 2. Pre-Install Script
[[FILE]]
Attr = { Run = "/bin/bash", Method = "install" }
INLINE = "./.plugin/pre-install.sh"

# 3. Source Package
[[FILE]]
Attr = { Name = "&source;.txz", Run = "upgradepkg --install-new --reinstall" }
URL = "&packageURL;"
MD5 = "&MD5;"

# 4. Post-Install Script
[[FILE]]
Attr = { Run = "/bin/bash", Method = "install" }
INLINE = "./.plugin/post-install.sh"

# 5. Removal Script
[[FILE]]
Attr = { Run = "/bin/bash", Method = "remove" }
CDATA = "./.plugin/remove.sh"
```

## Configuration Sections

### ENTITIES

The `[ENTITIES]` section defines variables for your plugin file, similar to XML entities in the `.plg` file. Entity references use XML syntax (`&entity;`) and can reference other entities defined earlier in the section. If `version` is not included, the version will be automatically generated in the standard format (yyyy.mm.dd.hhmm). If the MD5 is not included, the `packageURL` will automatically be downloaded and the MD5 will be generated.

All entities defined here will be:
1. Added to the XML DOCTYPE declaration
2. Used as attributes in the `<PLUGIN>` tag
3. Available for reference throughout the plugin using `&entityname;` syntax

### CHANGES

The `[CHANGES]` section specifies the location of your changelog file:
- `File` - Path to the changelog (absolute or relative to working directory)

The contents of this file will be embedded in the `<CHANGES>` section of the plugin.

### FILE

The `[[FILE]]` array defines files and operations for the plugin. Each `[[FILE]]` entry represents one file operation.

**Comments** - Standard TOML comments (`#`) are preserved and converted to XML comments in the output.

**Attr** - An inline table of XML attributes for the `<FILE>` tag:

- `Method` - Valid values: `"install"` or `"remove"`. Files with `install` run during plugin installation; files with `remove` run during plugin removal. Should not be used with `Name`.

- `Name` - Creates a file in the Unraid filesystem at the specified location. Requires either `INLINE` or `CDATA`. The contents of the file specified by `INLINE` or `CDATA` will be saved to this location. Should not be used with `Method`.

- `Mode` - Optionally sets the permissions of a file when used with `Name` (e.g., `"0775"`).

- `Run` - The command or file to run. For scripts, set to `"/bin/bash"` and use `INLINE` or `CDATA` to specify the script location. This runs the script without saving it to disk.

**Content Types:**

- `INLINE` - Path to a file whose contents will be injected into the plugin. With `INLINE`, XML entities are expanded. For example, if your script contains `echo &MD5;`, it will be expanded to `echo b31ca4f4cc86325d132739c93f79b922`. This can be useful but may make troubleshooting more difficult.

- `CDATA` - Path to a file whose contents will be injected into the plugin wrapped in `<![CDATA[...]]>`. This prevents entity expansion - everything in your script is injected as-is, making it easier to test and debug scripts independently.

- `URL` - A URL to download (typically used for package files).

- `MD5` - The MD5 hash of a downloaded file for verification.

## Usage

```bash
python toml_to_xml.py config.toml output.plg [base_path]
```

**Arguments:**
- `config.toml` - Input TOML configuration file
- `output.plg` - Output XML plugin file (optional, prints to stdout if omitted)
- `base_path` - Base path for resolving relative file paths (default: current directory)

**Example:**
```bash
python toml_to_xml.py plugin.toml bobbintb.system.dirt.plg
```

## Notes

- Entity references can reference other entities as long as they appear earlier in the `[ENTITIES]` section
- Comments in the TOML file are preserved in the XML output
- File paths in `INLINE`, `CDATA`, and `File` can be absolute or relative to the `base_path`
- The script uses case-insensitive matching for `INLINE` and `CDATA` keys
