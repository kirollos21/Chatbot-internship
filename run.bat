@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM ===================================================================
REM  Palm Hills Resident Assistant - Windows launcher
REM
REM    run.bat            setup + dataset + db + ingest + serve
REM    run.bat setup      create the venv, install dependencies
REM    run.bat dataset    rebuild + validate the policy dataset
REM    run.bat db         start PostgreSQL and wait for it
REM    run.bat db-stop    stop the local PostgreSQL
REM    run.bat ingest     load the dataset and build embeddings
REM    run.bat serve      run the API on http://localhost:8000
REM    run.bat test       run the test suite
REM    run.bat check      report what is installed / configured
REM    run.bat app        run the Flutter web app in Chrome
REM    run.bat android    run the Flutter app on an Android emulator
REM    run.bat app-build  build the Flutter web bundle
REM ===================================================================

cd /d "%~dp0"
set "ROOT=%CD%"
set "BACKEND=%ROOT%\backend"
set "VENV=%BACKEND%\.venv"
set "PY=%VENV%\Scripts\python.exe"

REM Portable PostgreSQL, used when no container runtime is installed.
set "PGBIN_LOCAL=D:\PHD\tools\pgsql\bin"
set "PGDATA_LOCAL=D:\PHD\tools\pgdata"
set "PGPORT_LOCAL=5433"

REM Android SDK. Android Studio installs here by default.
set "ANDROID_SDK=%LOCALAPPDATA%\Android\Sdk"
if defined ANDROID_HOME if exist "%ANDROID_HOME%\platform-tools\adb.exe" set "ANDROID_SDK=%ANDROID_HOME%"
REM The emulator reaches the host machine at 10.0.2.2, never at localhost -
REM inside the emulator localhost is the emulator itself.
set "ANDROID_API_BASE=http://10.0.2.2:8000"

set "CMD=%~1"
if "%CMD%"=="" set "CMD=all"

if /i "%CMD%"=="setup"     goto :setup
if /i "%CMD%"=="dataset"   goto :dataset
if /i "%CMD%"=="db"        goto :database
if /i "%CMD%"=="db-stop"   goto :dbstop
if /i "%CMD%"=="ingest"    goto :ingest
if /i "%CMD%"=="serve"     goto :serve
if /i "%CMD%"=="test"      goto :test
if /i "%CMD%"=="check"     goto :check
if /i "%CMD%"=="app"       goto :app
if /i "%CMD%"=="android"   goto :android
if /i "%CMD%"=="app-build" goto :appbuild
if /i "%CMD%"=="all"       goto :all
echo [ERROR] Unknown command "%CMD%".
echo         Use: setup ^| dataset ^| db ^| db-stop ^| ingest ^| serve ^| test ^| check
echo              app ^| app-build ^| android
exit /b 1

REM -------------------------------------------------------------------
:all
call :setup    || exit /b 1
call :dataset  || exit /b 1
call :database || exit /b 1
call :ingest   || exit /b 1
goto :serve

REM -------------------------------------------------------------------
:setup
echo.
echo === [1/4] Environment =============================================
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not on PATH. Install Python 3.12+ and re-run.
    exit /b 1
)
if not exist "%PY%" (
    echo Creating virtual environment in backend\.venv ...
    python -m venv "%VENV%" || exit /b 1
)
echo Installing dependencies ...
"%PY%" -m pip install --upgrade pip --quiet || exit /b 1
"%PY%" -m pip install -r "%BACKEND%\requirements.txt" --quiet || exit /b 1

if not exist "%ROOT%\.env" (
    echo Creating .env from .env.example ...
    copy /y "%ROOT%\.env.example" "%ROOT%\.env" >nul
    echo.
    echo   [ACTION NEEDED] Edit .env and set GEMINI_API_KEY before serving,
    echo   otherwise the assistant falls back to deterministic answers.
    echo.
)
echo Dependencies ready.
exit /b 0

REM -------------------------------------------------------------------
:dataset
echo.
echo === [2/4] Dataset =================================================
"%PY%" "%ROOT%\data\build_dataset.py" || (
    echo [ERROR] Dataset validation failed - see the errors above.
    exit /b 1
)
exit /b 0

REM -------------------------------------------------------------------
REM Prefer a container runtime when present: that image ships pgvector,
REM which is the production configuration. Otherwise fall back to the
REM local portable PostgreSQL, which has no pgvector - see VECTOR_ENABLED.
:database
echo.
echo === [3/4] Database ================================================
where docker >nul 2>&1
if not errorlevel 1 goto :dbdocker
if exist "%PGDATA_LOCAL%\postgresql.conf" goto :dblocal

echo [ERROR] No database available.
echo.
echo   Install a container runtime (Docker/Podman) for the pgvector
echo   image, or set up the portable PostgreSQL described in
echo   README.md "Running the database on Windows".
exit /b 1

:dbdocker
docker compose up -d postgres || exit /b 1
echo Waiting for PostgreSQL to accept connections ...
set /a TRIES=0
:waitdocker
set /a TRIES+=1
docker compose exec -T postgres pg_isready -U palmhills -d palmhills >nul 2>&1
if not errorlevel 1 goto :dbready
if !TRIES! GEQ 30 (
    echo [ERROR] PostgreSQL did not become ready in time.
    docker compose logs --tail 20 postgres
    exit /b 1
)
timeout /t 2 /nobreak >nul
goto :waitdocker

:dblocal
"%PGBIN_LOCAL%\pg_isready.exe" -h 127.0.0.1 -p %PGPORT_LOCAL% >nul 2>&1
if not errorlevel 1 (
    echo Local PostgreSQL already running on port %PGPORT_LOCAL%.
    goto :dbready
)
echo Starting local PostgreSQL on port %PGPORT_LOCAL% ...
"%PGBIN_LOCAL%\pg_ctl.exe" -D "%PGDATA_LOCAL%" -l "%PGDATA_LOCAL%\server.log" -w start
if errorlevel 1 (
    echo [ERROR] Local PostgreSQL did not start. See %PGDATA_LOCAL%\server.log
    exit /b 1
)

:dbready
echo PostgreSQL is ready.
exit /b 0

REM -------------------------------------------------------------------
:dbstop
if not exist "%PGDATA_LOCAL%\postgresql.conf" (
    echo No local PostgreSQL cluster at %PGDATA_LOCAL%.
    exit /b 0
)
"%PGBIN_LOCAL%\pg_ctl.exe" -D "%PGDATA_LOCAL%" -m fast stop
exit /b 0

REM -------------------------------------------------------------------
:ingest
echo.
echo === [4/4] Ingest ==================================================
pushd "%BACKEND%"
"%PY%" -m app.scripts.ingest
set "RC=!ERRORLEVEL!"
popd
if not "!RC!"=="0" (
    echo [ERROR] Ingest failed. Is the database running?  run.bat db
    exit /b 1
)
exit /b 0

REM -------------------------------------------------------------------
:serve
echo.
echo === Serving =======================================================
echo   API   http://localhost:8000
echo   Docs  http://localhost:8000/docs
echo   Stop  Ctrl+C
echo.
pushd "%BACKEND%"
"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
popd
exit /b 0

REM -------------------------------------------------------------------
:test
echo.
echo === Tests =========================================================
pushd "%BACKEND%"
"%PY%" -m pytest -q
set "RC=!ERRORLEVEL!"
popd
exit /b !RC!

REM -------------------------------------------------------------------
:check
echo.
echo === Environment check =============================================
where python >nul 2>&1 && (echo   python           OK) || (echo   python           MISSING)
if exist "%PY%" (echo   venv             OK) else (echo   venv             MISSING - run: run.bat setup)
if exist "%ROOT%\.env" (echo   .env             OK) else (echo   .env             MISSING - run: run.bat setup)
if exist "%ROOT%\data\palm_hills_regulations_v1.0.json" (echo   dataset          OK) else (echo   dataset          MISSING - run: run.bat dataset)
where docker >nul 2>&1 && (echo   docker           OK) || (echo   docker           MISSING)

if exist "%PGDATA_LOCAL%\postgresql.conf" (
    "%PGBIN_LOCAL%\pg_isready.exe" -h 127.0.0.1 -p %PGPORT_LOCAL% >nul 2>&1
    if errorlevel 1 (
        echo   local postgres   STOPPED - run: run.bat db
    ) else (
        echo   local postgres   RUNNING on port %PGPORT_LOCAL%
    )
) else (
    echo   local postgres   NOT SET UP
)

if exist "%ROOT%\.env" (
    findstr /b /c:"GEMINI_API_KEY=" "%ROOT%\.env" | findstr /r /c:"GEMINI_API_KEY=.\+" >nul 2>&1
    if errorlevel 1 (
        echo   GEMINI_API_KEY   NOT SET - answers fall back to deterministic templates
    ) else (
        echo   GEMINI_API_KEY   SET
    )
)
echo.
exit /b 0

REM -------------------------------------------------------------------
:findflutter
set "FLUTTER="
where flutter >nul 2>&1 && set "FLUTTER=flutter"
if not defined FLUTTER if exist "D:\PHD\tools\flutter\bin\flutter.bat" set "FLUTTER=D:\PHD\tools\flutter\bin\flutter.bat"
if not defined FLUTTER (
    echo [ERROR] Flutter SDK not found.
    echo         Install it, or place it at D:\PHD\tools\flutter
    exit /b 1
)
exit /b 0

REM -------------------------------------------------------------------
:app
call :findflutter || exit /b 1
echo.
echo === Flutter web app ===============================================
echo   Backend expected at http://localhost:8000
echo.
pushd "%ROOT%\frontend"
"%FLUTTER%" run -d chrome --dart-define=API_BASE_URL=http://localhost:8000
set "RC=!ERRORLEVEL!"
popd
exit /b !RC!

REM -------------------------------------------------------------------
:appbuild
call :findflutter || exit /b 1
pushd "%ROOT%\frontend"
"%FLUTTER%" build web --release --dart-define=API_BASE_URL=http://localhost:8000
set "RC=!ERRORLEVEL!"
popd
if "!RC!"=="0" echo Built frontend\build\web
exit /b !RC!
