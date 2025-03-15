#!/bin/bash

{
  ./yq -r '
    "<?xml version='\''1.0'\'' standalone='\''yes'\''?>\n\n" +
    "<!DOCTYPE PLUGIN [\n" +
    (.ENTITIES | to_entries | (map(.key | length) | max) as $max | (map("<!ENTITY " + .key + (" " * ($max +4 - (.key | length) + 1)) + " \"" + .value + "\">") | join("\n"))) +
    "\n]>\n" +
    (.ENTITIES | to_entries | map(.key + "=\"&" + .key + ";\"") | "<PLUGIN " + join(" ") + ">")
  ' plg.yaml

  ./yq -o xml '. as $root | {"CHANGES": $root.CHANGES}' plg.yaml

  ./yq --xml-attribute-prefix "$" ".FILES" -o xml  plg.yaml

} > output.xml

content=$(awk -v RS= 'match($0, /<CHANGES>([^<]*)<\/CHANGES>/, arr) {print arr[1]}' output.xml)
content=$(<"$content")
gawk -v content="$content" -i inplace '{gsub(/<CHANGES>.*<\/CHANGES>/, "<CHANGES>\n" content "\n</CHANGES>")} 1' output.xml

while IFS= read -r line
do
    if [[ $line =~ \<INLINE\>(.*)\</INLINE\> ]]; then
        filename="${BASH_REMATCH[1]}"
        if [ -f "$filename" ]; then
            content=$(cat "$filename")
            printf '%s\n' "${line/<INLINE>$filename<\/INLINE>/<INLINE>$'\n'<![CDATA[$'\n'$content$'\n']]>$'\n'<\/INLINE>}"
        else
            echo "File not found: $filename" >&2
            echo "$line"
        fi
    else
        echo "$line"
    fi
done < output.xml
