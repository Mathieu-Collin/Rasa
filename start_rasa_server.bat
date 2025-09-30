@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: =============================================================================
:: 🏥 Rasa Medical Chatbot - Server Launcher for Windows
:: =============================================================================
:: Interactive script to start the Rasa medical chatbot server
:: Supports multiple languages, deployment modes, and debugging options
:: =============================================================================

title Rasa Medical Chatbot - Server Launcher

echo.
echo ========================================================================
echo 🏥 RASA MEDICAL CHATBOT - SERVER LAUNCHER
echo ========================================================================
echo Interactive script to launch your medical stroke data analysis chatbot
echo.

:: Check if we're in the correct directory
if not exist "src\core\config.yml" (
    echo ❌ ERROR: config.yml not found!
    echo Please run this script from the Rasa project root directory.
    echo Current directory: %CD%
    pause
    exit /b 1
)

:: Set Python path for custom components
set PYTHONPATH=%CD%;%CD%\src

:main_menu
cls
echo.
echo ========================================================================
echo 🏥 RASA MEDICAL CHATBOT - MAIN MENU
echo ========================================================================
echo.
echo Choose your startup method:
echo.
echo 1. 🚀 Quick Start (French - Production Ready)
echo 2. 🧪 Interactive Shell (Debug Mode)
echo 3. 🌐 API Server (REST endpoints)
echo 4. 🐳 Docker Mode
echo 5. 🔧 Advanced Configuration
echo 6. 🌍 Multi-language Setup
echo 7. ❓ Help & Troubleshooting
echo 8. 🚪 Exit
echo.
set /p choice="Enter your choice (1-8): "

if "%choice%"=="1" goto quick_start
if "%choice%"=="2" goto interactive_shell
if "%choice%"=="3" goto api_server
if "%choice%"=="4" goto docker_mode
if "%choice%"=="5" goto advanced_config
if "%choice%"=="6" goto multilang_setup
if "%choice%"=="7" goto help_menu
if "%choice%"=="8" goto exit_script
echo Invalid choice. Please try again.
timeout /t 2 >nul
goto main_menu

:quick_start
cls
echo.
echo 🚀 QUICK START - French Medical Chatbot
echo ========================================
echo.
echo This will start the French version of the medical chatbot in production mode.
echo.
echo ⏳ Building model for French (fr/FR)...
call scripts\layer_rasa_lang.sh fr/FR
if errorlevel 1 (
    echo ❌ Model building failed!
    goto error_handler
)

echo.
echo ✅ Model built successfully!
echo 🌐 Starting Rasa server on http://localhost:5005
echo.
echo 💡 Test with: "Montrez-moi les données DTN pour les patients masculins"
echo.
rasa run --enable-api --cors "*" --endpoints src\core\endpoints.yml
goto main_menu

:interactive_shell
cls
echo.
echo 🧪 INTERACTIVE SHELL - Debug Mode
echo ==================================
echo.
echo Starting interactive shell for testing and debugging.
echo This mode allows you to chat directly with the bot.
echo.
echo Available test commands:
echo - "Hello" / "Bonjour" - Greetings
echo - "Show me DTN data" - Request visualization
echo - "Vis mig NIHSS data" (Danish) - Multilingual test
echo - "/restart" - Restart conversation
echo - "/stop" - Exit shell
echo.
pause
echo.
echo 🔄 Starting interactive shell...
rasa shell --debug --endpoints src\core\endpoints.yml
goto main_menu

:api_server
cls
echo.
echo 🌐 API SERVER MODE
echo ==================
echo.
echo Choose API configuration:
echo.
echo 1. Standard API (Port 5005)
echo 2. Custom Port
echo 3. Production Mode (no CORS)
echo 4. Development Mode (full CORS)
echo 5. Back to main menu
echo.
set /p api_choice="Enter your choice (1-5): "

if "%api_choice%"=="1" (
    set PORT=5005
    set CORS_MODE=--cors "*"
    goto start_api
)
if "%api_choice%"=="2" (
    set /p PORT="Enter port number (default 5005): "
    if "!PORT!"=="" set PORT=5005
    set CORS_MODE=--cors "*"
    goto start_api
)
if "%api_choice%"=="3" (
    set PORT=5005
    set CORS_MODE=
    goto start_api
)
if "%api_choice%"=="4" (
    set PORT=5005
    set CORS_MODE=--cors "*"
    goto start_api
)
if "%api_choice%"=="5" goto main_menu
echo Invalid choice.
timeout /t 2 >nul
goto api_server

:start_api
echo.
echo 🌐 Starting API Server...
echo Port: !PORT!
echo CORS: !CORS_MODE!
echo.
echo 📡 API will be available at: http://localhost:!PORT!
echo.
echo 🧪 Test with curl:
echo curl -X POST http://localhost:!PORT!/webhooks/rest/webhook \
echo      -H "Content-Type: application/json" \
echo      -d "{\"sender\": \"test\", \"message\": \"Show me stroke data\"}"
echo.
rasa run --enable-api !CORS_MODE! --port !PORT! --endpoints src\core\endpoints.yml
goto main_menu

:docker_mode
cls
echo.
echo 🐳 DOCKER MODE
echo ===============
echo.
echo Choose Docker operation:
echo.
echo 1. Build Docker image
echo 2. Run existing image
echo 3. Build and run (French)
echo 4. Build and run (Danish)
echo 5. Build and run (English)
echo 6. Interactive Docker shell
echo 7. Back to main menu
echo.
set /p docker_choice="Enter your choice (1-7): "

if "%docker_choice%"=="1" goto docker_build
if "%docker_choice%"=="2" goto docker_run
if "%docker_choice%"=="3" goto docker_build_run_fr
if "%docker_choice%"=="4" goto docker_build_run_da
if "%docker_choice%"=="5" goto docker_build_run_en
if "%docker_choice%"=="6" goto docker_interactive
if "%docker_choice%"=="7" goto main_menu
echo Invalid choice.
timeout /t 2 >nul
goto docker_mode

:docker_build
echo.
echo 🔨 Building Docker image...
docker build -t rasa-medical-chatbot .
echo ✅ Docker image built!
pause
goto docker_mode

:docker_run
echo.
echo 🚀 Running Docker container...
echo Server will be available at http://localhost:5005
docker run -p 5005:5005 rasa-medical-chatbot
goto docker_mode

:docker_build_run_fr
echo.
echo 🇫🇷 Building and running French version...
docker build --build-arg LAYERS="src/core src/locales/fr/FR" -t rasa-medical-fr .
docker run -p 5005:5005 rasa-medical-fr
goto docker_mode

:docker_build_run_da
echo.
echo 🇩🇰 Building and running Danish version...
docker build --build-arg LAYERS="src/core src/locales/da/DK" -t rasa-medical-da .
docker run -p 5005:5005 rasa-medical-da
goto docker_mode

:docker_build_run_en
echo.
echo 🇺🇸 Building and running English version...
docker build --build-arg LAYERS="src/core src/locales/en/US" -t rasa-medical-en .
docker run -p 5005:5005 rasa-medical-en
goto docker_mode

:docker_interactive
echo.
echo 🐳 Starting interactive Docker shell...
docker run -it rasa-medical-chatbot rasa shell
goto docker_mode

:advanced_config
cls
echo.
echo 🔧 ADVANCED CONFIGURATION
echo ==========================
echo.
echo 1. Train model with specific language
echo 2. Train multilingual model
echo 3. Dry-run (test without training)
echo 4. Debug mode with statistics
echo 5. Custom endpoints configuration
echo 6. Back to main menu
echo.
set /p adv_choice="Enter your choice (1-6): "

if "%adv_choice%"=="1" goto train_specific_lang
if "%adv_choice%"=="2" goto train_multilingual
if "%adv_choice%"=="3" goto dry_run_mode
if "%adv_choice%"=="4" goto debug_stats_mode
if "%adv_choice%"=="5" goto custom_endpoints
if "%adv_choice%"=="6" goto main_menu
echo Invalid choice.
timeout /t 2 >nul
goto advanced_config

:train_specific_lang
echo.
echo Available languages:
echo - fr/FR (French)
echo - da/DK (Danish)
echo - en/US (English)
echo - de/DE (German)
echo - es/ES (Spanish)
echo.
set /p lang_code="Enter language code (e.g., fr/FR): "
if "!lang_code!"=="" set lang_code=fr/FR
echo.
echo 🏋️ Training model for !lang_code!...
call scripts\layer_rasa_lang.sh !lang_code!
echo ✅ Training completed!
pause
goto advanced_config

:train_multilingual
echo.
echo 🌍 Training multilingual model with French, English, and Danish...
call scripts\layer_rasa_projects.sh "src/core src/locales/fr/FR src/locales/en/US src/locales/da/DK"
echo ✅ Multilingual training completed!
pause
goto advanced_config

:dry_run_mode
echo.
set /p lang_code="Enter language for dry-run test (default: fr/FR): "
if "!lang_code!"=="" set lang_code=fr/FR
echo.
echo 🧪 Running dry-run test for !lang_code!...
call scripts\layer_rasa_lang.sh --dry-run !lang_code!
pause
goto advanced_config

:debug_stats_mode
echo.
echo 🔍 Starting server in debug mode with statistics collection...
echo This will provide detailed logging and performance metrics.
echo.
rasa run --enable-api --cors "*" --debug --endpoints src\core\endpoints.yml
goto advanced_config

:custom_endpoints
echo.
echo Current endpoints file: src\core\endpoints.yml
echo.
set /p custom_endpoints="Enter custom endpoints file path (or press Enter for default): "
if "!custom_endpoints!"=="" set custom_endpoints=src\core\endpoints.yml
echo.
echo 🔌 Starting server with custom endpoints: !custom_endpoints!
rasa run --enable-api --cors "*" --endpoints "!custom_endpoints!"
goto advanced_config

:multilang_setup
cls
echo.
echo 🌍 MULTI-LANGUAGE SETUP
echo ========================
echo.
echo Available language combinations:
echo.
echo 1. 🇫🇷 French only (fr/FR)
echo 2. 🇩🇰 Danish only (da/DK)
echo 3. 🇺🇸 English only (en/US)
echo 4. 🇫🇷🇺🇸 French + English
echo 5. 🇩🇰🇺🇸 Danish + English
echo 6. 🇫🇷🇩🇰🇺🇸 All three languages
echo 7. 🔧 Custom combination
echo 8. Back to main menu
echo.
set /p lang_choice="Enter your choice (1-8): "

if "%lang_choice%"=="1" (
    set LANGUAGES=src/core src/locales/fr/FR
    goto start_multilang
)
if "%lang_choice%"=="2" (
    set LANGUAGES=src/core src/locales/da/DK
    goto start_multilang
)
if "%lang_choice%"=="3" (
    set LANGUAGES=src/core src/locales/en/US
    goto start_multilang
)
if "%lang_choice%"=="4" (
    set LANGUAGES=src/core src/locales/fr/FR src/locales/en/US
    goto start_multilang
)
if "%lang_choice%"=="5" (
    set LANGUAGES=src/core src/locales/da/DK src/locales/en/US
    goto start_multilang
)
if "%lang_choice%"=="6" (
    set LANGUAGES=src/core src/locales/fr/FR src/locales/da/DK src/locales/en/US
    goto start_multilang
)
if "%lang_choice%"=="7" (
    echo Enter custom language combination (space-separated):
    echo Example: src/core src/locales/fr/FR src/locales/de/DE
    set /p LANGUAGES="Languages: "
    goto start_multilang
)
if "%lang_choice%"=="8" goto main_menu
echo Invalid choice.
timeout /t 2 >nul
goto multilang_setup

:start_multilang
echo.
echo 🌍 Building multilingual model...
echo Languages: !LANGUAGES!
echo.
call scripts\layer_rasa_projects.sh "!LANGUAGES!"
if errorlevel 1 (
    echo ❌ Multilingual model building failed!
    goto error_handler
)
echo.
echo ✅ Multilingual model ready!
echo 🌐 Starting server...
rasa run --enable-api --cors "*" --endpoints src\core\endpoints.yml
goto main_menu

:help_menu
cls
echo.
echo ❓ HELP & TROUBLESHOOTING
echo =========================
echo.
echo 🔧 Common Issues and Solutions:
echo.
echo Problem: "layered_importer module not found"
echo Solution: Ensure PYTHONPATH is set correctly (automatically done by this script)
echo.
echo Problem: "Permission denied on scripts"
echo Solution: Run: icacls scripts\*.sh /grant Everyone:(RX)
echo.
echo Problem: "Port 5005 already in use"
echo Solution: Stop existing Rasa process or use different port
echo.
echo Problem: "Docker build failed"
echo Solution: Ensure Docker Desktop is running
echo.
echo Problem: "Model training failed"
echo Solution: Check data files and run: rasa data validate
echo.
echo 🧪 Test Commands:
echo.
echo Interactive Shell Tests:
echo - Hello / Bonjour / Hej (greetings)
echo - Show me DTN data for male patients
echo - Vis mig NIHSS data for kvinder (Danish)
echo - Montrez-moi les données stroke (French)
echo.
echo API Tests:
echo curl -X POST http://localhost:5005/webhooks/rest/webhook \
echo      -H "Content-Type: application/json" \
echo      -d "{\"sender\": \"test\", \"message\": \"Show stroke data\"}"
echo.
echo 📚 Documentation:
echo - Full README: README.md
echo - Rasa Docs: https://rasa.com/docs/
echo - Project Structure: See src/ directory
echo.
pause
goto main_menu

:error_handler
echo.
echo ❌ An error occurred during execution.
echo.
echo 🔍 Troubleshooting steps:
echo 1. Check if all required files exist
echo 2. Verify Python and Rasa installation
echo 3. Ensure proper permissions on script files
echo 4. Check the logs above for specific error messages
echo.
echo 💡 Try running the diagnostic script:
echo python analyze_diet_classifier.py
echo.
pause
goto main_menu

:exit_script
cls
echo.
echo 👋 Thank you for using Rasa Medical Chatbot!
echo.
echo 🏥 This chatbot helps analyze stroke patient data and generate
echo    medical visualizations in multiple languages.
echo.
echo 📚 For more information, check the README.md file.
echo.
echo Have a great day! 🌟
echo.
pause
exit /b 0
