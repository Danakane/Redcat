# Redcat

A remote shell handler implemented in python for CTF, pentest and red team engagements.


## Features:
* A session manager for handling mutiple listeners and shells at once.
* Bind and reverse shells support.
* TCP and SSL/TLS protocols support.
* IPv4 and IPv6 support.
* Fully interactive pty shell for Linux hosts.
* Basic data exfiltration for file download and upload.
* Limited windows support (no pty).
* Internal command-line completion.


redcat handles the low level communications and allow the user to easily manage the remote shells and automate some actions like file upload and download.

redcat mostly supports linux target platforms but minimal also provide minimal support for windows targets.


## Sessions

A session represents a single instance of communication between the attacker and a remote shell.

Sessions can be created via listeners for reverse shells or directly using the `connect` command for bind shells.

Sessions can be listed using the command `show sessions`

The user can "select" a session that would act as the default session commands are called for when no session id is provided by the user.
To select a session the user can use the command `session` followed by the session's id. `session none` command can be used to unselect the currently selected session.
Note: if no session is selected, the next created session with be automatically selected.

The user can spawn a shell for a given session using the command `shell` or alternatively if the session is selected by pressing `CTRL+D`.

To pause a session's shell and go back to redcat main console, the user must press `CTRL+D`

Finally to terminate a session, the user can call the `kill session` command or `exit` the tool.


## Listeners

Listeners are used to catch reverse shells.

redcat supports both IPv4 addresses, IPv6 addresses and hostnames. 
If for a given hostname, multiple bind addresses are possible then redcat will bind on all of them.

If no host or address are provided by the user then redcat will use "::" as default address. 

A listener can be created using the `listen` command. If the `-b, --background` flag is provided then the listener will run in the background.
Otherwise the listener will only accept a single reverse shell.

To terminate a listener,  the user can call the `kill listener` command or `exit` the tool. 

## Protocols

redcat supports tcp and ssl/tls protocols.

## Platforms

redcat supports mostly linux targets platform: Upon receiving a new linux connection (either bind a shell or a reverse shell) it will performe the following actions:
* Disabling shell command-line history
* Enumerate usefuls binaries using `which`.
* Spawn a pty shell for a fully interactive shell session
* Normalize the shell prompt

For windows, no particular action are performed, however CTRL+C events are ignored.

## Upload/Download

redcat provide basic data exfiltration using base64 encoding. While it can easily download any file, the upload function is much more limited in performance and can't be used to transfert any file bigger than a few Mb.

file uploads can be performed via the `upload` command.

file downloads can be performed via the `download` command.

## Capture

![redcat.png](img/redcat.png)
