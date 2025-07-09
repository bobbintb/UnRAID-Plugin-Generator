Plugin files in Unraid are essentially XML files but they can be difficult to read, especially if you include inline scripts. The version and MD5 also need to be updated every update, which can be a small chore. This script will create a *.plg for Unraid from a supplied YAML file. A sample YAML file is included for reference and using it should be self-evident:

```
ENTITIES:
  name : bobbintb.system.dirt
  author : bobbintb
  repo : UnRAID-DiRT
  tag : test
  launch : Settings/Deduplication in Real-Time
  pluginURL : https://github.com/&author;/&repo;/releases/download/&tag;/&name;.plg
  packageURL : https://github.com/&author;/&repo;/releases/download/&tag;/&name;.txz
  source : /boot/config/plugins/&name;/&name;
  icon : fa-search-minus
  min : 6.1.9
  version : 2025.02.11
  MD5 : b31ca4f4cc86325d132739c93f79b922
CHANGES: ./README.md
FILE:
- #STARTUP SCRIPT
  '@Name': /etc/rc.d/rc.dirt
  '@Mode': '0775'
  INLINE: ./.plugin/rc.dirt
- #PRE-INSTALL SCRIPT
  '@Run': /bin/bash
  '@Method': install
  INLINE: ./.plugin/pre-install.sh
- #SOURCE PACKAGE
  '@Name': "&source;.txz"
  '@Run': "upgradepkg --install-new --reinstall"
  URL: "&packageURL;"
  MD5: "&MD5;"
- #POST-INSTALL SCRIPT
  '@Run': /bin/bash
  '@Method': install
  INLINE: ./.plugin/post-install.sh
- #NOFILES
  '@Run': /bin/bash
  '@Method': remove
  INLINE: ./.plugin/remove.sh
```

**ENTITIES**

The entities section looks pretty much the same as it does in the plg file. It's essentially the variables for your plugin file. As you can see, an entity can reference another entity as long as it comes before it. If the `version` entity is absent, the script will download current version of the plugin (specified as `pluginURL`) and automatically add the correct version to the entites in the standard date/letter version format that Unraid plugins use. If the MD5 entity is absent, it will download the source package specified in `packageURL`, calculate the hash, and add the MD5 entity.

**CHANGES**

This is the location of the change log. It can be absolute or relative to working directory.

**FILE**

This section defines the files and is the most complicated and confusing part of a plugin file. This script aims to significantly reduce that.

  `-` Denotes the start of a file entry. 

  `#` Interpreted as comments and are retained when converted to the plg file.

  `@` Interpreted as an attribute or method for the XML tag. 
  
  `@Method` Valid methods are `install` and `remove`. File entries with the `install` method will be ran when the plugin is installed and file entries with the `remove` method will be ran when the plugin is removed. Updating a plugin will run `remove` and `install`. Should not be used with `@Name`.
  
  `@Name` Used to create a file in the Unraid filesystem at the specified location. Requires either `INLINE` or `CDATA`. The contents of the file specified by `INLINE` or `CDATA` will be saved to the location on Unirad specified in `@Name`. Should not be used with `@Method`.
  
  `@Mode` Optionally sets the permissions of a file when used with `@Name`.
  
  `@Run` The command or file to run. If running a script, set it to `/bin/bash` and use `INLINE` or `CDATA` as the location of the script to inject into the plugin file. This will run the script without saving it to disk.
  
  `INLINE` The location of the script to inject into the plugin file. With INLINE, entities are expanded. Using the above YAML as an example, if your script has `echo &MD5;`, it will be expanded to `echo b31ca4f4cc86325d132739c93f79b922`. This can be useful but having XML entities in your script can make troubleshooting and testing your scripts more difficult.
  
  `CDATA` The location of the script to inject into the plugin file. Simply a special variant of INLINE that does not expand entities. Everything in your script is injected into the plugin file as-is.
