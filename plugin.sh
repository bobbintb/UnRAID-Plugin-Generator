#!/bin/bash

# Load the config file
CONFIG_FILE="./plugin.cfg"
if [[ -f "$CONFIG_FILE" ]]; then
  . $CONFIG_FILE
else
  echo "Config file not found: $CONFIG_FILE"
  exit 1
fi

OUTPUT_FILE="${name}.plg"

create_entity() {
longest_key_length=$(awk -F'=' '/=/{l=length($1); if(l>max) max=l} END {print max}' "$CONFIG_FILE")
target_key_length=$((longest_key_length + 3))

while IFS= read -r line; do
    if [[ $line == *"="* ]]; then
        keys+=("${line%%=*}")
    fi
done < $CONFIG_FILE

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
  tar -cJf "${name}".txz --owner=0 --group=0 /
  popd
}

package_plugin
md5Hash=$(md5sum "${name}.txz" | awk '{print $1}')

PLUGIN="<?xml version='1.0' standalone='yes'?>

<!DOCTYPE PLUGIN ["

create_entity

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
