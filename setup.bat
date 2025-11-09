@echo on
pip install -r req.txt
pip install requests_toolbelt
pip uninstall aiohttp urllib3 -y
pip install aiohttp==3.8.6 urllib3==1.26.6
pip install aiogram==2.25.2
pip install requests==2.28.1
pip install coloredlogs
pip install selenium
pip install webdriver-manager
pause