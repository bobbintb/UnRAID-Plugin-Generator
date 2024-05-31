#!/bin/bash

show_help() {
  echo "Usage: $0 [options]"
  echo
  echo "Options:"
  echo "  -a, --author    The author of the plugin."
  echo "  -c, --config    Specify config file location. (default: ./plugin.cfg)"
  echo "  -i, --input	  The directory of the plugin's source code. (default: ./src/)"
  echo "  -m, --md5       The MD5 hash of the plugin *.txz file. (required but automatically provided)"
  echo "  -n, --name      The name of the plugin. (required)"
  echo "  -r, --repo      The name of the git repo for the plugin."
  echo "  -u, --url       The URL of the *.plg file. (required for automatic checking and updating of the plugin)"
  echo "  -v, --version   The version of the plugin. If not specified it will be generated in the standard Limetech format (e.g 2023.07.21a)"
  echo
  echo "  -l, --min       The minimun version of UnRAID allowed for the plugin. Typically used to prevent compatibility issues."
  echo "  -x, --max       The maximum version of UnRAID allowed for the plugin. Typically used to prevent compatibility issues."
  echo "  -h, --help      Display this help message."

  exit 0
}
config="./plugin.cfg"
OPTIONS=$(getopt -o a:c:i:m:n:r:u:v:l:x:h --long author:,config:,input:,md5:,name:,repo:,url:,version:,min:,max:,help -- "$@")
eval set -- "$OPTIONS"

# Load the config file
if [[ -f "$config" ]]; then
  . $config
else
  echo "Config file not found: $config"
  exit 1
fi

OUTPUT_FILE="${name}.plg"

create_entity() {
longest_key_length=$(awk -F'=' '/=/{l=length($1); if(l>max) max=l} END {print max}' "$config")
target_key_length=$((longest_key_length + 3))

while IFS= read -r line; do
    if [[ $line == *"="* ]]; then
        keys+=("${line%%=*}")
    fi
done < $config

for key in "${keys[@]}"; do
  new_key=$(printf "%-${target_key_length}s" "$key")
  echo "$new_key"
  PLUGIN="${PLUGIN}
<!ENTITY ${new_key}\"${!key}\">"
  done
  PLUGIN="${PLUGIN}
]>"
}

package_plugin() {
  dest="./tmp/usr/local/emhttp/plugins/${name}"
  mkdir -p "$dest"
  echo "Copying files to temporary folder to archive..."
  cp -r "${plugin_src}"* "$dest"
  echo "Archiving..."
  pushd ./tmp
  tar -cJf ../"${name}".txz --owner=0 --group=0 usr/*
  popd
}

package_plugin
md5Hash=$(md5sum "${name}.txz" | awk '{print $1}')

PLUGIN="<?xml version='1.0' standalone='yes'?>

<!DOCTYPE PLUGIN ["

create_entity

PLUGIN="${PLUGIN}
<PLUGIN name="&name;" author="&author;" version="&version;" launch="&launch;" pluginURL="&pluginURL;" icon="fa-search-minus" min="6.1.9">

<CHANGES>
##&name;

</CHANGES>"

if [[ -e "./sh/pre-install.sh" ]]; then
  PLUGIN="${PLUGIN}

<!-- PRE-INSTALL SCRIPT -->
<FILE Run="/bin/bash" Method="install">
<INLINE>
$(<./sh/pre-install.sh)
</INLINE>
</FILE>"
fi

if [[ -e "./sh/install.sh" ]]; then
  PLUGIN="${PLUGIN}

<!-- INSTALL SCRIPT -->
<FILE Run="/bin/bash" Method="install">
<INLINE>
$(<./sh/install.sh)
</INLINE>
</FILE>"
fi

if [[ -e "./sh/post-install.sh" ]]; then
  PLUGIN="${PLUGIN}

<!-- POST-INSTALL SCRIPT -->
<FILE Run="/bin/bash" Method="install">
<INLINE>
$(<./sh/post-install.sh)
</INLINE>
</FILE>"
fi

if [[ -e "./sh/remove.sh" ]]; then
  PLUGIN="${PLUGIN}

<!-- REMOVE SCRIPT -->
<FILE Run="/bin/bash" Method="remove">
<INLINE>
$(<./sh/remove.sh)
</INLINE>
</FILE>"
fi

if [[ -e "./sh/files.txt" ]]; then
  PLUGIN="${PLUGIN}

<!-- SOURCE FILES -->
$(<./sh/files.txt)"
fi

PLUGIN="${PLUGIN}

</PLUGIN>"

echo "${PLUGIN}" > "${OUTPUT_FILE}"
