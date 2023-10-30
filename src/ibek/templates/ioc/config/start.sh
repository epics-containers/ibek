#! /bin/bash

echo '
Generic IOC start script ...

Launch this Generic IOC with configuration folder mounted over
/epics/ioc/config in order to create an IOC instance.

Choices of contents of the config folder are:

 1. ioc.yaml *************************************************************
    If the config folder contains an ioc.yaml file we invoke the ibek tool to
    generate the startup script and database. Then launch with the generated
    startup script.

 2. st.cmd + ioc.subst *********************************************************
    If the config folder contains a st.cmd script and a ioc.subst file then
    optionally generate ioc.db from the ioc.subst file and use the st.cmd script
    as the IOC startup script. Note that the expanded database file will
    be generated in /tmp/ioc.db

 3. start.sh ******************************************************************
    If the config folder contains a start.sh script it will be executed.
    This allows the instance implementer to provide a conmpletely custom
    startup script.

 4. empty config folder *******************************************************
    If the config folder is empty the default startup script prints the message
    you are reading now.

 RTEMS IOCS - RTEMS IOC startup files can be generated using 2,3,4 above. For
 RTEMS we do not execute the ioc inside of the pod. Instead we:
  - copy the IOC directory to the RTEMS mount point
  - send a reboot command to the RTEMS crate
  - start a telnet session to the RTEMS IOC console

'

# This is a placeholder script, but we still need keep the container running.
# Wait indefinitely so the container does not exit and restart continually.
while true; do
    sleep 1
done
