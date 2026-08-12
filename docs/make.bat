@ECHO OFF
SETLOCAL ENABLEDELAYEDEXPANSION

pushd %~dp0

REM ---- Configuration (mirrors Makefile) ----
IF "%SPHINXBUILD%"=="" SET SPHINXBUILD=uv run python -m sphinx.cmd.build
IF "%SPHINXOPTS%"=="" SET SPHINXOPTS=

SET SOURCEDIR=source
SET BUILDDIR=build\html
SET EXAMPLE_NAME=flync_example
SET EXAMPLE_SOURCE=..\examples\
SET EXAMPLE_DST=source\_static\

REM ---- Ensure sphinx-build (via uv) works ----
%SPHINXBUILD% >NUL 2>NUL
IF ERRORLEVEL 9009 (
    ECHO.
    ECHO Sphinx build command was not found.
    ECHO Make sure uv and Sphinx are installed.
    ECHO.
    EXIT /B 1
)

REM ---- Default target = help ----
IF "%1"=="" GOTO help

IF /I "%1"=="html" GOTO html
IF /I "%1"=="help" GOTO help

REM Fallback to Sphinx -M targets like the original script
%SPHINXBUILD% -M %1 %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
GOTO end

:help
%SPHINXBUILD% -M help %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
GOTO end

:html
ECHO Copying example project...
xcopy /E /I /Y "%EXAMPLE_SOURCE%%EXAMPLE_NAME%" "%EXAMPLE_DST%%EXAMPLE_NAME%" >NUL

IF ERRORLEVEL 1 (
    ECHO Failed to copy example files.
    GOTO end
)

ECHO Creating Mermaid schematics...
uv run python source\_scripts\create_mermaid.py
IF ERRORLEVEL 1 (
    ECHO Mermaid generation failed.
    GOTO cleanup
)

ECHO Building HTML documentation...
%SPHINXBUILD% -b html "%SOURCEDIR%" "%BUILDDIR%"
IF ERRORLEVEL 1 (
    ECHO Sphinx build failed.
    GOTO cleanup
)

:cleanup
ECHO Cleaning temporary files...

REM Remove copied example
rmdir /S /Q "%EXAMPLE_DST%%EXAMPLE_NAME%" 2>NUL

REM Remove generated mermaid directory
rmdir /S /Q "%EXAMPLE_DST%mermaid" 2>NUL

:end
popd
ENDLOCAL
