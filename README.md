# UnRAID Plugin Generator

This tool converts **TOML** configurations into Unraid-compatible `.plg` XML files. It automates tedious tasks like Slackware packaging, MD5 checksum calculation, versioning, and script embedding.

## Requirements

```bash
pip install tomlkit
```

## Comprehensive TOML Example

This example demonstrates a complex plugin structure including web UI files, binaries, and system scripts.

```toml
[ENTITIES]
name = "my.awesome.plugin"
author = "developer"
repo = "unraid-plugin-repo"
tag = "v1.0.0"
launch = "Settings/MyPlugin"
# Note: version and MD5 omitted to trigger auto-generation
pluginURL = "https://github.com/&author;/&repo;/releases/download/&tag;/&name;.plg"
packageURL = "https://github.com/&author;/&repo;/releases/download/&tag;/&name;.txz"
icon = "fa-shield"
min = "6.12.0"

[CHANGES]
File = "./CHANGELOG.md"

# --- SYSTEM FILES ---

# 1. Configuration File (Only created if missing)
[[FILE]]
Attr = { Name = "/boot/config/plugins/&name;/&name;.cfg", Mode = "0664" }
SCRIPT_RAW = "./assets/default_config.cfg"

# 2. Icon File
[[FILE]]
Attr = { Name = "/usr/local/emhttp/plugins/&name;/images/&name;.png" }
URL = "https://raw.githubusercontent.com/&author;/&repo;/&tag;/assets/icon.png"

# --- INSTALLATION ---

# 3. Main Slackware Package
# The script will auto-calculate &MD5; if it's used here but missing from [ENTITIES]
[[FILE]]
Attr = { Name = "&source;.txz", Run = "upgradepkg --install-new --reinstall" }
URL = "&packageURL;"
MD5 = "&MD5;"

# 4. Pre-Install Logic (Entity-aware)
[[FILE]]
Attr = { Run = "/bin/bash", Method = "install" }
SCRIPT_TEMPLATE = "./scripts/pre-install.sh"

# --- UNINSTALLATION ---

# 5. Cleanup Script (Literal injection)
[[FILE]]
Attr = { Run = "/bin/bash", Method = "remove" }
SCRIPT_RAW = "./scripts/uninstall-cleaner.sh"
```

## Core Functionality

### 1. Smart Entity Management
The script automatically manages the XML `<!ENTITY>` block:
* **Auto-Version:** If `version` is missing from `[ENTITIES]`, it generates one based on the current timestamp (`yyyy.mm.dd.hhmm`).
* **Auto-MD5:** If `MD5` is missing, the script will attempt to hash the file found at `packageURL` or the local package created via the `--package-source` flag.
* **Variable Injection:** Use `&entityname;` anywhere in your TOML or in files linked via `SCRIPT_TEMPLATE`.

### 2. Script Embedding Modes
* **SCRIPT_TEMPLATE:** Reads the local file and injects it into the XML. Unraid **will** parse this for entities (e.g., `echo &version;` becomes `echo 2026.04.11`).
* **SCRIPT_RAW:** Wraps the file content in a `<![CDATA[ ... ]]>` block. Unraid will treat this as a literal string, which is safer for complex scripts containing characters like `&` or `$`.

### 3. Automated Packaging
Using the `--package-source` flag allows you to point to a local directory or a **Git URL**. The script will:
1. Clone the repository (if a URL is provided).
2. Download the Slackware `makepkg` utility.
3. Compress the source into a `.txz` Slackware package.
4. Move the package to your output directory.

---

## Usage

```bash
python toml_to_xml.py [toml_file] [options]
```

### Command Line Arguments
| Argument | Description |
| :--- | :--- |
| `-o`, `--output` | Path for the generated `.plg` file. |
| `-p`, `--package-source` | Path or Git URL to build a Slackware `.txz` from. |
| `-b`, `--base-path` | Root directory for resolving local file paths (default: `.`). |
| `--entity KEY=VALUE` | Add/Override an entity (e.g., `--entity tag=v1.1.0`). |
| `--changes PATH` | Path to the changelog file. |
| `--file JSON` | Manually add a file entry using a JSON string. |

### Example Commands

**Build from TOML with local packaging:**
```bash
python toml_to_xml.py plugin.toml -p ./src -o plugin.plg
```

**Build directly from a remote GitHub repository:**
```bash
python toml_to_xml.py plugin.toml -p https://github.com/user/my-plugin -o plugin.plg
```

---

## Technical Notes
* **Comments:** Standard TOML comments (`#`) placed directly above `[[FILE]]` entries are converted into XML comments in the final output.
* **Permissions:** Use the `Mode` attribute (e.g., `"0775"`) within the `Attr` table to set Linux file permissions during installation.
