@echo off
rem ===========================================================================
rem  L'Iliade, o il poema della forza - rigenerazione del sito
rem
rem    run.bat              verifica il corpus, rigenera le sezioni, rende docs\
rem    run.bat anteprima    rigenera le sezioni e apre l'anteprima ricaricabile
rem    run.bat verifica     controlla soltanto: corpus, sezioni, allineamento
rem
rem  Non modifica mai corpus\: la traduzione si scrive solo li'.
rem ===========================================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "MODO=%~1"
if "%MODO%"=="" set "MODO=sito"

if /i not "%MODO%"=="sito" if /i not "%MODO%"=="anteprima" if /i not "%MODO%"=="verifica" (
  echo [errore] argomento sconosciuto: %MODO%
  echo Uso: run.bat [anteprima^|verifica]
  exit /b 2
)

rem --- interprete: il virtualenv del progetto se c'e', altrimenti quello di sistema
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

"%PYTHON%" --version >nul 2>&1
if errorlevel 1 (
  echo [errore] Python non trovato. Serve Python 3.10 o piu' recente, con PyYAML:
  echo     python -m pip install PyYAML
  exit /b 1
)

"%PYTHON%" -c "import yaml" >nul 2>&1
if errorlevel 1 (
  echo [errore] manca PyYAML. Installarlo con:
  echo     "%PYTHON%" -m pip install PyYAML
  exit /b 1
)

rem --- accenti corretti nei messaggi degli script
set "PYTHONUTF8=1"

rem --- scripts\ sul path: i moduli si trovano fra loro senza installazione
set "PYTHONPATH=%CD%\scripts;%PYTHONPATH%"

rem --- Quarto serve solo quando si renderizza o si apre l'anteprima
if /i not "%MODO%"=="verifica" (
  set "QUARTO=quarto"
  where quarto >nul 2>&1
  if errorlevel 1 (
    rem Installazione standard per utente: in alcuni ambienti `where` non la
    rem vede anche se la cartella di Quarto compare nel PATH.
    if exist "%LOCALAPPDATA%\Programs\Quarto\bin\quarto.exe" (
      set "QUARTO=%LOCALAPPDATA%\Programs\Quarto\bin\quarto.exe"
    ) else (
      echo [errore] quarto non e' nel PATH. Installarlo da https://quarto.org/docs/get-started/
      exit /b 1
    )
  )
)

if /i "%MODO%"=="verifica" goto :verifica

echo.
echo == verifico il corpus ==
"%PYTHON%" scripts\validate_corpus.py --consenti-traduzione
if errorlevel 1 goto :fallito

echo.
echo == genero le sezioni da corpus\it\ ==
"%PYTHON%" scripts\build_site.py
if errorlevel 1 goto :fallito

if /i "%MODO%"=="anteprima" (
  echo.
  echo == anteprima: Ctrl+C per chiudere ==
  call "%QUARTO%" preview site
  if errorlevel 1 goto :fallito
  goto :fine
)

echo.
echo == renderizzo il sito in docs\ (HTML + saggio in PDF) ==
call "%QUARTO%" render site
if errorlevel 1 goto :fallito

echo.
echo Fatto. Il sito reso e' in docs\ ^(apri docs\index.html^);
echo il saggio in PDF e' docs\iliade-poema-forza.pdf.
echo Per pubblicare: git add corpus site docs ^&^& git commit ^&^& git push
goto :fine

:verifica
echo.
echo == impronte del corpus ==
"%PYTHON%" scripts\build_manifest.py --check
if errorlevel 1 goto :fallito

echo.
echo == corpus, sezioni e stato della traduzione ==
"%PYTHON%" scripts\validate_corpus.py --consenti-traduzione
if errorlevel 1 goto :fallito

echo.
echo == corpus italiano allineato al francese ==
"%PYTHON%" scripts\build_corpus_it.py --check
if errorlevel 1 goto :fallito

echo.
echo == site\sezione-*.qmd allineate al corpus ==
"%PYTHON%" scripts\build_site.py --check
if errorlevel 1 goto :fallito

echo.
echo Tutti i controlli sono passati.
goto :fine

:fallito
echo.
echo [errore] passaggio fallito ^(codice %errorlevel%^): niente e' stato pubblicato.
exit /b 1

:fine
endlocal
