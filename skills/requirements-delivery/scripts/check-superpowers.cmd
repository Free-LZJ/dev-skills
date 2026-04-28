@echo off
setlocal EnableExtensions

rem Check superpowers availability for requirements-delivery skill.
rem Output: installed | declined | not-installed
rem Exit code: 0=installed, 1=declined, 2=not-installed

set "CACHE=%USERPROFILE%\.agents\.superpowers-status"

if exist "%CACHE%" (
    set /p STATUS=<"%CACHE%"
    if /i "%STATUS%"=="installed" (
        echo installed
        exit /b 0
    )
    if /i "%STATUS%"=="declined" (
        echo declined
        exit /b 1
    )
)

set "FOUND="
for %%D in ("%USERPROFILE%\.agents\skills" "%USERPROFILE%\.claude\skills") do (
    for %%S in ("brainstorming" "writing-plans" "systematic-debugging") do (
        if exist "%%~D\%%~S\" (
            set "FOUND=1"
            goto :found
        )
    )
)

echo not-installed
exit /b 2

:found
if not exist "%USERPROFILE%\.agents" mkdir "%USERPROFILE%\.agents"
>%CACHE% echo installed
echo installed
exit /b 0
