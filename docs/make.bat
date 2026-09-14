@ECHO OFF
SETLOCAL ENABLEDELAYEDEXPANSION

pushd %~dp0

REM ---- Configuration (mirrors Makefile) ----
IF "%SPHINXBUILD%"=="" SET SPHINXBUILD=uv run python -m sphinx.cmd.build
IF "%SPHINXOPTS%"=="" SET SPHINXOPTS=

SET SOURCEDIR=source
SET BUILDDIR=build
SET EXAMPLE_NAME=flync_example
SET EXAMPLE_NAME2=flync_example_experimental
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
IF /I "%1"=="generations" CALL :generations & GOTO end
IF /I "%1"=="clear" CALL :clear & GOTO end
IF /I "%1"=="help" GOTO help

REM Fallback to Sphinx -M targets like the original script
%SPHINXBUILD% -M %1 %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
GOTO end

:help
%SPHINXBUILD% -M help %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
GOTO end

:html
CALL :generations
IF ERRORLEVEL 1 GOTO end

ECHO Copying example projects...
xcopy /E /I /Y "%EXAMPLE_SOURCE%%EXAMPLE_NAME%" "%EXAMPLE_DST%%EXAMPLE_NAME%" >NUL
xcopy /E /I /Y "%EXAMPLE_SOURCE%%EXAMPLE_NAME2%" "%EXAMPLE_DST%%EXAMPLE_NAME2%" >NUL

ECHO Building HTML documentation...
%SPHINXBUILD% -M html %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
IF ERRORLEVEL 1 (
    ECHO Sphinx build failed.
)

CALL :clear
GOTO end

:generations
ECHO Creating Mermaid schematics...
uv run python source\_scripts\create_mermaid.py
IF ERRORLEVEL 1 (
    ECHO Mermaid generation failed.
    EXIT /B 1
)

ECHO Creating ECU variant diagrams...
uv run python source\_scripts\generate_ecu_diagram.py "%EXAMPLE_SOURCE%ecu_variants" -o "%EXAMPLE_DST%images\ecu_variants"
IF ERRORLEVEL 1 (
    ECHO ECU diagram generation failed.
    EXIT /B 1
)

ECHO Generating CLI usage docs...
uv run typer flync_cli.main utils docs --name flync --title Usage --output "%SOURCEDIR%\flync_cli\usage.md"
IF ERRORLEVEL 1 (
    ECHO CLI usage doc generation failed.
    EXIT /B 1
)

ECHO Generating error catalog...
uv run python ..\src\flync_cli\main.py errors generate-catalog
IF ERRORLEVEL 1 (
    ECHO Error catalog generation failed.
    EXIT /B 1
)
EXIT /B 0

:clear
ECHO Clearing generated files...
REM Remove mermaid files
rmdir /S /Q "%EXAMPLE_DST%mermaid" 2>NUL
REM Remove ecu_variant diagrams
rmdir /S /Q "%EXAMPLE_DST%images\ecu_variants" 2>NUL
REM Remove flync_example
rmdir /S /Q "%EXAMPLE_DST%%EXAMPLE_NAME%" 2>NUL
rmdir /S /Q "%EXAMPLE_DST%%EXAMPLE_NAME2%" 2>NUL
REM Remove generated cli usage page
del /Q "%SOURCEDIR%\flync_cli\usage.md" 2>NUL
EXIT /B 0

:end
popd
ENDLOCAL
