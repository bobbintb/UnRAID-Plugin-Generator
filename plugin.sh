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

package_plugin() {
  dest="./tmp/usr/local/emhttp/plugins/${name}"
  mkdir -p "$dest"
  echo "Copying files to temporary folder to archive..."
  cp -r "${plugin_src}"* "$dest"
  echo "Archiving..."
  pushd ./tmp
  tar -cJf ../"${name}".txz --owner=0 --group=0 usr/*
  popd
  rm -dr ./tmp
}

create_entity() {
while IFS= read -r line; do
    if [[ $line == *"="* ]]; then
        keys+=("${line%%=*}")
    fi
done < $config
keys+=("version")
keys+=("MD5")
max=$(( $(printf "%s\n" "${keys[@]}" | awk '{ print length }' | sort -nr | head -1) + 3 ))
for key in "${keys[@]}"; do
  new_key=$(printf "%-${max}s" "$key")
  PLUGIN+="<!ENTITY ${new_key}\"${!key}\">"$'\n'
  done
  new_key=$(printf "%-${max}s" "")
  PLUGIN+="]>"$'\n'
}

package_plugin

PLUGIN="<?xml version='1.0' standalone='yes'?>"$'\n'
PLUGIN+=""$'\n'
PLUGIN+="<!DOCTYPE PLUGIN ["$'\n'

create_entity

PLUGIN+="<PLUGIN"
for key in "${keys[@]}"; do
  PLUGIN+=" ${key}=\"&${key};\""
done
PLUGIN+=">"$'\n'$'\n'
PLUGIN+="<CHANGES/>"$'\n'

if [[ -e "./sh/files.txt" ]]; then
  PLUGIN+="<!-- SOURCE FILES -->
$(<./sh/files.txt)"$'\n'
fi

if [[ -e "./sh/pre-install.sh" ]]; then
  PLUGIN+="<!-- PRE-INSTALL SCRIPT -->
<FILE Run="/bin/bash" Method="install">
<INLINE>
$(<./sh/pre-install.sh)
</INLINE>
</FILE>"$'\n'$'\n'
fi

if [[ -e "./sh/install.sh" ]]; then
  PLUGIN+="<!-- INSTALL SCRIPT -->
<FILE Run="/bin/bash" Method="install">
<INLINE>
$(<./sh/install.sh)
</INLINE>
</FILE>"$'\n'$'\n'
fi

if [[ -e "./sh/post-install.sh" ]]; then
  PLUGIN+="<!-- POST-INSTALL SCRIPT -->
<FILE Run="/bin/bash" Method="install">
<INLINE>
$(<./sh/post-install.sh)
</INLINE>
</FILE>"$'\n'$'\n'
fi

if [[ -e "./sh/remove.sh" ]]; then
  PLUGIN+="<!-- REMOVE SCRIPT -->
<FILE Run="/bin/bash" Method="remove">
<INLINE>
$(<./sh/remove.sh)
</INLINE>
</FILE>"$'\n'$'\n'
fi

PLUGIN+="</PLUGIN>"

echo "${PLUGIN}" > "${OUTPUT_FILE}"

md5Hash=$(md5sum "${name}.txz" | awk '{print $1}')
sed -i 's/^\(<!ENTITY MD5 "\).*\("\)/\1'"$md5sum"'\2/' ${OUTPUT_FILE}
