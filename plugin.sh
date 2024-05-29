#!/bin/bash

CONFIG_FILE="./plugin.cfg"

if [[ -f "$CONFIG_FILE" ]]; then
  declare -A config
  keys=()  # Indexed array to store keys
  while IFS="=" read -r key value; do
    [[ $key == \#* ]] || [[ -z $key ]] && continue
    config[$key]=$value
    keys+=("$key")  # Store key in indexed array
  done < "$CONFIG_FILE"

else
  echo "Config file not found: $CONFIG_FILE"
  exit 1
fi

read_and_modify_config() {
  longest_key_length=0
  
  # Find the length of the longest key
  for key in "${keys[@]}"; do
    if [[ ${#key} -gt $longest_key_length ]]; then
      longest_key_length=${#key}
    fi
  done
  
  # Calculate the target length for keys
  target_key_length=$((longest_key_length + 1))

  echo "<?xml version='1.0' standalone='yes'?>"
  echo ""
  echo "<!DOCTYPE PLUGIN ["

  # Print modified key-value pairs with padded keys
  for key in "${keys[@]}"; do
    new_key=$(printf "%-${target_key_length}s" "$key")
    new_value="${config[$key]}"
    echo "<!ENTITY ${new_key}${new_value}>"
  done
}

read_and_modify_config
