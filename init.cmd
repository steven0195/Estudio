@echo off
CMD  /C git status
CMD  /C git add .
CMD  /C git status
CMD  /C git commit -m "[UPDATE] up to %date%"
CMD  /C git push
exit