import os
import sys
import asyncio
import gc
import logging
import threading
import time
from dotenv import load_dotenv

# Limit native background threads
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

# Always resolve files relative to this bot's folder
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Set UTF-8 encoding & unbuffered output for console
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

# Load environment variables
dotenv_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_file)

from utils.time_utils import setup_ist_logging, now_ist, YunaLogFormatter

# Initialize IST logging
setup_ist_logging()
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("discord.webhook.async_").setLevel(logging.ERROR)

# Event Loop tuning
if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass
else:
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        pass

# High-frequency garbage collection for minimum RAM footprint
gc.set_threshold(1000, 10, 10)

from core import BotBase

def main():
    token = os.environ.get("SUPREME_TOKEN") or os.environ.get("TOKEN") or os.environ.get("DISCORD_TOKEN")
    if not token:
        print("❌ ERROR: SUPREME_TOKEN or DISCORD_TOKEN not found in .env!")
        print("Please configure your dedicated Security Bot token in .env file.")
        sys.exit(1)

    while True:
        ist_str = now_ist().strftime("%Y-%m-%d %I:%M:%S %p IST")
        print(f"🛡️ Starting Yuna Supreme (Dedicated Security & Moderation Bot)... [{ist_str}]")
        bot_instance = BotBase()
        try:
            bot_instance.run(token, log_level=20, log_formatter=YunaLogFormatter())
            break
        except KeyboardInterrupt:
            shutdown_ist = now_ist().strftime("%Y-%m-%d %I:%M:%S %p IST")
            print(f"\n[YUNA SUPREME] Graceful shutdown completed. [{shutdown_ist}]")
            sys.exit(0)
        except Exception as e:
            err_ist = now_ist().strftime("%Y-%m-%d %I:%M:%S %p IST")
            print(f"⚠️ [YUNA SUPREME] Gateway disconnect: {e} [{err_ist}]. Reconnecting in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    main()
