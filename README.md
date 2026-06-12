# neostab

yaml-inspired fstab generator

it's pronounced 'neo stab'

## why

writing fstab files sucks, and using something like
rclone mounts with lots of options makes it even
worse.

for an example; this is what an /etc/fstab entry
looks like that uses the default options copyparty
recommends on their page for mounting to a linux PC
and 'rclone mount's guidance:

```
copyparty-dav: /mnt/copyparty rclone rw,noauto,nofail,_netdev,x-systemd.automount,args2env,vfs_cache_mode=writes,dir_cache_time=5s,config=/etc/rclone.conf,cache_dir=/var/cache/rclone,allow_other 0 0
```

i feel like it should be self explanatory that this is
utterly impossible to read.

and that example doesn't even show all the problems i
have; take for example the fact any whitespace
character is used as a seperator,

or that if you want to set the desktop display name
of a given mount you're supposed to use the
'x-gvfs-name' option that only supports HTTP style
percent encoded strings, and you can't even nessecarily
use the '+' character for spaces to make it more human
readable.

i found myself, when i was writing fstab files,
spending a lot of time worrying about inputting
stuff right and modifying a bunch of duplicate options
between different lines, distracting me from anything
else i may have been doing.

### overview and what i feel improves on fstab

here is the example from above rewritten in neostab's
config format:

```
#neostab

/mnt/copyparty
    device: copyparty-dav:
    type: rclone
    options:
        rw
        noauto
        nofail
        _netdev
        x-systemd.automount
        args2env
        vfs_cache_mode: writes
        dir_cache_time: 5s
        config: /etc/rclone.conf
        cache_dir: /var/cache/rclone
        allow_other
```

and you know what's even better?? if you have another
mount that uses almost the same options you can
inherit the config from that one!

```
/mnt/copyparty2
    extends: /mnt/copyparty
    device: copyparty2-dav:
```

neostab supports 'phony' mounts that exist only
so that they may be inherited:

```
fat32_readonly
    phony
    type: vfat
    options:
        ro

/mnt/archive
    extends: fat32_readonly
    device: UUID=1234-ABCD
    options:
        nofail
    check: 2
```

```
UUID=1234-ABCD  /mnt/archive    vfat    ro,nofail   0 2
```

neostab also allows you to specify options to automatically
create the mountpoints, as well, so that you can
use it as a tool to set up your mountpoints
quickly on new systems:

```
example
    phony
    mkdir
    group: users
    user: 1000
    mode: 777
```

the group and user attributes can be either IDs (like
the numbers listed in `/etc/passwd`) or names.

the mode is in octal, like what you input into `chmod`.

neostab, when installing /etc/fstab, will check to see
if the mountpoint exists, and what its mode and owners
are to decide whether it needs to change them to match
the config file, or create the directory (and its
parents -- `os.makedirs`/`mkdir -p`).

# usage

neostab reads config files from `/etc/neostab.d`
and overwrites `/etc/fstab`, creates directories
for mounts that have the `mkdir` attribute, and
changes the file modes and owner to match what
the config file says if specified, and runs
`systemctl daemon-reload` if the `systemctl` binary
is found on your system (as `mount` likes to complain
if you don't after changing `fstab`.)

neostab has a simulation mode, which is triggered
by running it as non-root. it will check existence*
and modes* of mountpoints, inform whether it would
change anything or make directories, and print out
the fstab it would write.

*which may not be accurate because you're not root
if you're in simulation mode

# config syntax

### top-level fields (sections and defines), comments, and indentation

Empty lines or lines that start with ';' (even if indented) are ignored.

'Top-level' lines are either mountpoint definitions
(sections), defines (mappings that start with a `#`),
or the neostab config file signature (`#neostab`).

Indentation is used hierarchically, like how YAML
and Python source code use it.

Indentation can be any amount of spaces or tabs
but must be consistent (otherwise neostab will crash).

Neostab 'learns' the indentation of a file by however
much whitespace precedes the line after the first
section.

There are three other different kinds of configuration
fields; flags, mappings, and blocks.

## fields

### blocks

`options` is an example of a block.

Blocks can contain any of the non-top-level config
field types (although, there is no use to having a
block within a block at this time.)

They must be followed by a colon, and then a newline,
and imply that the indentation level will increase.

```
 -> options: <-
        ...
```

### flags

`phony`, and most mount options like `rw` are examples
of flags.

Flags are lines that do not have a colon in them
at all. This is useful for options that do not
require an argument, with the software only caring
whether they're specified at all.

```
 -> phony <-
    options:
     -> rw <-
```

### mappings

`type`, `device`, and less common mount options like
`uid`, `gid`, and `x-gvfs-name` are examples of
mappings.

Mappings are key and value pairs, written as the
field name followed by its value, any string of
characters terminated by the end of the line.

There is no sort of escaping or quoting for mapping
values; they aren't parsed as anything but a string
unless it's required for a feature to function (like
the `mode` or `group` attributes.)

```
    phony
    options:
        rw
     -> x-gvfs-name: Photos of explosives <-
 -> type: ext4 <-
```

# all supported config options (and default values)

## signature, defines

```
#neostab
```

Neostab config file signature. Files that do not have
this as the very first line in them will be ignored.

```
#priority: 0
```

Defines the order that neostab outputs this file's
mountpoints relative to others.

The contents of a neostab config with a greater 
priority value show up before configs with lesser
priority values in `/etc/fstab`.

The usual unix-y thing to do is just add a number
to the front of your config file to make it load
first but since neostab configs are self-contained,
I like this more.

```
(any string that doesn't start with #)
```

Defines a new mountpoint. The line of text should
contain the directory you expect something to be
mounted in. Equivalent to `fs_file`, the second field
in a line in `fstab`.

This implies that the next line should be indented.

## mountpoint settings

### phony

```
phony
```

Flag to not actually output this mountpoint to
`/etc/fstab`, also skipping checks for values that
can't be empty (like `type` and `device`)

### device

```
device: no default value (required for non-phony)
```

Mapping that defines what device file will be passed
for mounts. Equivalent to `fs_spec`, the first field
in a line in `fstab`.

### type

```
type: no default value (required for non-phony)
```

Mapping that defines the filesystem type.

Equivalent to `fs_vfstype`, the third field in a line
in `fstab`.

### options

```
options:
    ...
```

Set of flags and mappings to pass to the mount program.

`x-gvfs-...` mappings are treated specially;
their values are percent-encoded by neostab so that
you can write mount names in plain text.

Any flag that starts with an exclamation mark (`!`)
removes the flag or mapping with a matching name.

I use this for negating flags like `x-gvfs-show`, so
that I can extend a section that has a flag like that
and then negate it later.

```
network_share
    phony
    options:
        x-gvfs-show

/mnt/share
    extends: network_share
    options:
        !x-gvfs-show
        x-gvfs-hide
```

If option order matters, flags can actually be used
as placeholders as well when extending:

```
options_example_1
    phony
    options:
        option_1
        option_2

        ; 'option_1,option_2'

options_example_2
    phony
    extends: options_example_1
    options:
        option_1: new value
        !option_2
        option_3: a third second thing

        ; 'option_1=new\040value,option_3=a\040third\040second\040thing'
```

### check

```
check: 0
```

Default value is 0, this is equivocal to `fs_passno`,
fstab field 6.

If `check` is a flag, it will be treated as if its
value is '1'.

This is used at boot time to determine filesystem
check order.

0 (default) doesn't request that `fsck` checks it,
`1` means it'll be checked first, and any higher
value will be checked after the lesser ones.

### dump

```
dump: 0
```

Default value is 0, this is equivocal to `fs_freq`,
fstab field 5.

If `dump` is a flag, it will be treated as if its
value is '1'.

This is used by the ext2/3 backup utility `dump`
which is probably not relevant to you.

### mkdir

```
mkdir
```

If specified, this mountpoint will be created by
neostab when `/etc/fstab` is installed by it.

If `mode` is not specified the directories will be
created with mode `777`.

### user, group

```
user: no default
group: no default
```

If specified, the mountpoint directory will be checked
for if the owner matches, and will be changed to match
if it does not.

neostab parses these as numbers first, and if it's not
a valid number, it attempts to look up the values
specified as group and user names.

### mode

```
mode: 777 (not enforced)
```

If specified, the mountpoint directory's file mode
will be set to the given value if it does not already
match.

neostab parses `mode` as an octal number, like what
is input to `chmod`.
