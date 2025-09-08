@echo off
setlocal enabledelayedexpansion

REM === Config ===
set API_URL=https://www.pranayai.com/ingest
set DATA_DIR=data

echo Starting bulk ingest at %date% %time% > success.log
echo Starting bulk ingest at %date% %time% > error.log

REM === Loop through PDFs in the data folder ===
for %%F in ("%DATA_DIR%\*.pdf") do (
    echo Uploading %%~nxF ...
    curl -s -X POST "%API_URL%" -F "files=@\"%%F\"" > tmp_response.json

    findstr /C:"ingested" tmp_response.json >nul
    if !errorlevel! == 0 (
        echo SUCCESS: %%~nxF >> success.log
        echo   -> OK
    ) else (
        echo ERROR: %%~nxF >> error.log
        type tmp_response.json >> error.log
        echo   -> FAILED
    )
)

del tmp_response.json
echo Done! Check success.log and error.log for details.
pause
