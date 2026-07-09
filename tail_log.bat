@echo off
color 0A
powershell -NoExit -Command "Get-Content 'C:\ecosis\ECOnnect\econnect.log' -Wait -Tail 10