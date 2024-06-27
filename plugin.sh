-#!/bin/bash

show_help() {
  echo "Usage: $0 [options]"
  echo
  echo "Options:"
  echo "  -a, --author    The author of the plugin."
  echo "  -c, --config    Specify config file location. (default: ./plugin.cfg)"
  echo "  -i, --input	    The directory of the plugin's source code. (default: ./src/)"
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

#####################package_plugin#####################
#                                                      #
package_plugin() {
  dest="../tmp/usr/local/emhttp/plugins/${name}"
  mkdir -p "$dest"
  echo "Copying files to temporary folder to archive..."
  rsync -av --exclude=".*" --exclude='plugin.sh' --exclude='sh/' ./ "$dest"
  pushd ../tmp
  #tar -cJf ../"${name}".txz --owner=0 --group=0 usr/*
  makepkg ../"${name}".txz <<< n
  popd
  rm -dr ../tmp
  MD5=$(md5sum "../${name}.txz" | awk '{print $1}')
  echo "Package hash: $MD5}"

}
#                                      #
########################################
#####################create_entity#####################
#                                                     #
create_entity() {
  keys=()
  while IFS='=' read -r line; do
    if [[ $line == *"="* ]]; then
      keys+=("${line%%=*}")
    fi
  done < "$config"

  keys+=("version")
  keys+=("MD5")
  max=$(( $(printf "%s\n" "${keys[@]}" | awk '{ print length }' | sort -nr | head -1) + 3 ))
  for key in "${keys[@]}"; do
    case "$key" in
      "version")
        value="$version"
        ;;
      "MD5")
        value="$MD5"
        ;;
      *)
        value="${!key}"
        ;;
    esac

    new_key=$(printf "%-${max}s" "$key")
    PLUGIN+="<!ENTITY ${new_key}\"$value\">"$'\n'
  done
  PLUGIN+="]>"$'\n'
}

#                                      #
########################################
#####################getver#####################
#                                              #
getver(){
# get current date and previous version
          version=$(date +"%Y.%m.%d")
          datepattern='ENTITY version\s+"([^"]+)"'
          echo "Current date: ${version}"
          previousVersion=$(grep -oP '<!ENTITY version\s*"\K[^"]*' $OUTPUT_FILE)
          echo "Previous version: ${previousVersion}"

          # determine new version
          if [[ $version == $previousVersion ]]; then
          version+="a"
          echo "New version: ${version}"
          fi
          if [[ $version == ${previousVersion%?} && "$previousVersion" =~ [[:alpha:]]$ ]]; then
          extracted_letter=${previousVersion: -1}
          echo "Previous sub-version: ${extracted_letter}"
          ascii_code=$(printf "%d" "'$extracted_letter")
          next_ascii_code=$((ascii_code + 1))
          next_letter=$(printf \\$(printf '%03o' "$next_ascii_code"))
          version+="$next_letter"
          echo "TAG=$($version)" >> $GITHUB_ENV
          #echo "New version: ${version}"
          fi
}
#                                      #
########################################

########################################################################################################################################################################
# Check if makepkg is installed
if ! command -v makepkg >/dev/null 2>&1; then
    echo "makepkg is not installed"
    exit 1
fi

# Load the config file
config="./plugin.cfg"
if [[ -f "$config" ]]; then
  echo "Loading settings from config file: $config"
  . $config
else
  echo "Config file not found: $config"
  exit 1
fi
OUTPUT_FILE="${name}.plg"

#####################
package_plugin
getver
########################################

PLUGIN="<?xml version='1.0' standalone='yes'?>"$'\n'
PLUGIN+=""$'\n'
PLUGIN+="<!DOCTYPE PLUGIN ["$'\n'

create_entity

PLUGIN+="<PLUGIN"
for key in "${keys[@]}"; do
  PLUGIN+=" ${key}=\"&${key};\""
done
PLUGIN+=">"$'\n'$'\n'

PLUGIN+="<CHANGES>"$'\n'
if [[ -e "CHANGELOG.md" ]]; then
  PLUGIN+=$(<CHANGELOG.md)$'\n'
fi
PLUGIN+="</CHANGES>"$'\n'$'\n'

#####################################
if [[ -e "./.plugin/files.txt" ]]; then
  PLUGIN+="<!-- SOURCE FILES -->
$(<./.plugin/files.txt)"$'\n'$'\n'
fi

if [[ -e "./.plugin/pre-install.sh" ]]; then
  PLUGIN+="<!-- PRE-INSTALL SCRIPT -->
<FILE Run=\"/bin/bash\" Method=\"install\">
<INLINE>
$(<./.plugin/pre-install.sh)
</INLINE>
</FILE>"$'\n'$'\n'
fi

PLUGIN+="<!-- SOURCE PACKAGE -->
<FILE Name=\"&source;.txz\" Run=\"upgradepkg --install-new --reinstall\">
<URL>https://raw.githubusercontent.com/&author;/&repo;/release/artifacts/&name;.txz</URL>
<MD5>&MD5;</MD5>
</FILE>"$'\n'$'\n'

if [[ -e "./.plugin/install.sh" ]]; then
  PLUGIN+="<!-- INSTALL SCRIPT -->
<FILE Run=\"/bin/bash\" Method=\"install\">
<INLINE>
$(<./.plugin/install.sh)
</INLINE>
</FILE>"$'\n'$'\n'
fi

if [[ -e "./.plugin/post-install.sh" ]]; then
  PLUGIN+="<!-- POST-INSTALL SCRIPT -->
<FILE Run=\"/bin/bash\" Method=\"install\">
<INLINE>
$(<./.plugin/post-install.sh)
</INLINE>
</FILE>"$'\n'$'\n'
fi

if [[ -e "./.plugin/remove.sh" ]]; then
  PLUGIN+="<!-- REMOVE SCRIPT -->
<FILE Run=\"/bin/bash\" Method=\"remove\">
<INLINE>
$(<./.plugin/remove.sh)
</INLINE>
</FILE>"$'\n'$'\n'
fi

PLUGIN+="</PLUGIN>"
###############################################
echo "${PLUGIN}" > "${OUTPUT_FILE}"
