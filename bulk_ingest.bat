@echo off
set API=https://www.pranayai.com/ingest

echo Uploading all PDFs/TXTs/MDs from data\ ...

for %%f in (data\*.pdf data\*.txt data\*.md) do (
  echo   Ingesting %%f ...
  curl -s -X POST "%API%" -F "files=@\"%%f\""
)

echo Done!
pause
