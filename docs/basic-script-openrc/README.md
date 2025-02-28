## Basic init youtube-local for openrc

1. Write `/etc/init.d/youtube-local` file.

```
#!/sbin/openrc-run
# Distributed under the terms of the GNU General Public License v3 or later
name="youtube-local"
pidfile="/var/run/youtube-local.pid"
command="/usr/sbin/youtube-local"

depend() {
    use net
}

start_pre() {
    if [ ! -f /usr/sbin/youtube-local ] ; then
        eerror "Please create script file of youtube-local in '/usr/sbin/youtube-local'"
        return 1
    else
        return 0
    fi
}

start() {
    ebegin "Starting youtube-local"
    start-stop-daemon --start --exec "${command}" --pidfile "${pidfile}"
    eend $?
}

reload() {
    ebegin "Reloading ${name}"
    start-stop-daemon --signal HUP --pidfile "${pidfile}"
    eend $?
}

stop() {
   ebegin "Stopping ${name}"
   start-stop-daemon --quiet --stop --exec "${command}" --pidfile "${pidfile}"
   eend $?
}
```

after, modified execute permissions:

    $ doas chmod a+x /etc/init.d/youtube-local


2. Write `/usr/sbin/youtube-local` and configure path.

```
#!/usr/bin/env bash

cd /home/your-path/youtube-local/ # change me
source venv/bin/activate
python server.py > /dev/null 2>&1 &
echo $! > /var/run/youtube-local.pid
```

after, modified execute permissions:

    $ doas chmod a+x /usr/sbin/youtube-local


3. OpenRC check

- status: `doas rc-service youtube-local status`
- start: `doas rc-service youtube-local start`
- restart: `doas rc-service youtube-local restart`
- stop: `doas rc-service youtube-local stop`

- enable: `doas rc-update add youtube-local default`
- disable: `doas rc-update del youtube-local`

When youtube-local is run with administrator privileges,
the configuration file is stored in /root/.youtube-local
