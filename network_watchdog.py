import asyncio
import sqlite3
import logging
import platform
from datetime import datetime

# ==========================================
# تنظيمات (Configuration)
# ==========================================
DB_PATH = r"D:\folder_project_city\CounterCNC\database_customer_club_test.db"
# ليست IP بردهاي شما (به عنوان مثال 37 دستگاه)
BOARD_IPS = [
    "192.168.1.3",
    "192.168.1.101",
    "192.168.1.105",
    "192.168.1.106",
    "192.168.1.107",
    "192.168.1.109",
    "192.168.1.115",
    "192.168.1.119",
    "192.168.1.121",
    "192.168.1.123",
    "192.168.1.126",
    "192.168.1.129",
    "192.168.1.130",
    "192.168.1.132",
    "192.168.1.134",
    "192.168.1.136",
    "192.168.1.138",
    "192.168.1.139",
    "192.168.1.145",
    "192.168.1.148",
    "192.168.1.150",
    "192.168.1.156",
    "192.168.1.158",
    "192.168.1.161",
    "192.168.1.162",
    "192.168.1.164",
    "192.168.1.167",
    "192.168.1.168",
    "192.168.1.169",
    "192.168.1.173",
    "192.168.1.176",
    "192.168.1.188",
    "192.168.1.190",
    "192.168.1.191",
    "192.168.1.192",
    "192.168.1.194",
    "192.168.1.196"
]
CHECK_INTERVAL = 5  # هر چند ثانيه يک بار شبکه بررسي شود؟

# حد آستانه براي تشخيص وضعيت شبکه (انعطاف در برابر خاموش بودن يکي دو دستگاه)
MIN_DOWN_TO_CONSIDER_OFFLINE = len(BOARD_IPS) - 8  # اگر 13 دستگاه قطع بودند، يعني شبکه قطع است
MIN_UP_TO_CONSIDER_ONLINE = len(BOARD_IPS) - 10     # اگر 12 دستگاه وصل شدند، يعني شبکه برگشته است

# تنظيمات لاگر
logging.basicConfig(
    filename='network_watchdog.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ==========================================
# توابع کمکي
# ==========================================
async def ping_ip(ip):
    """
    يک IP را به صورت غيرهمزمان (Async) پينگ مي‌کند.
    در صورت موفقيت True و در صورت شکست False برمي‌گرداند.
    """
    # پارامتر پينگ در ويندوز -n و در لينوکس -c است
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    
    # اجراي دستور پينگ در بک‌گراند بدون نمايش خروجي در ترمينال
    process = await asyncio.create_subprocess_exec(
        'ping', param, '1', '-w', '1000', ip,  # Timeout = 1000ms
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await process.wait()
    return process.returncode == 0

def insert_reconnect_marker():
    """
    پکت 400 را به عنوان سيگنال اتصال مجدد (Jitter Buffer Trigger) در ديتابيس ثبت مي‌کند.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # استفاده از datetime('now', 'localtime') براي ثبت زمان دقيق ويندوز
            cursor.execute("""
                INSERT INTO WAL_DECODED (packet_id, decoded_data, insert_time) 
                VALUES (400, '{"event": "network_reconnected", "source": "watchdog"}', datetime('now', 'localtime'))
            """)
            conn.commit()
            logging.info("Packet 400 (Reconnect Marker) successfully inserted into database.")
    except Exception as e:
        logging.error(f"Failed to insert Packet 400 into database: {e}")

# ==========================================
# منطق اصلي مانيتورينگ
# ==========================================
async def network_monitor():
    logging.info("Network Watchdog started. Monitoring 15 CNC boards...")
    print("Watchdog is running... (Press Ctrl+C to stop)")
    
    # در ابتدا فرض مي‌کنيم شبکه وصل است تا اگر قطع شد متوجه شويم
    is_network_down = False 
    
    while True:
        try:
            # پينگ کردن همه آي‌پي‌ها به صورت موازي (زمان اجراي اين خط معادل کندترين پينگ است، نه مجموع آن‌ها)
            ping_tasks = [ping_ip(ip) for ip in BOARD_IPS]
            results = await asyncio.gather(*ping_tasks)
            
            up_count = sum(results)
            down_count = len(BOARD_IPS) - up_count
            
            # 1. بررسي قطعي شبکه
            if down_count >= MIN_DOWN_TO_CONSIDER_OFFLINE:
                if not is_network_down:
                    is_network_down = True
                    logging.warning(f"NETWORK DOWN DETECTED! {down_count}/{len(BOARD_IPS)} boards are unreachable.")
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] NETWORK DOWN!")

            # 2. بررسي وصل شدن مجدد شبکه
            elif up_count >= MIN_UP_TO_CONSIDER_ONLINE:
                if is_network_down:
                    is_network_down = False
                    logging.info(f"NETWORK RECONNECTED! {up_count}/{len(BOARD_IPS)} boards are back online.")
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] NETWORK RECONNECTED! Inserting Packet 400...")
                    
                    # ثبت سيگنال بافر ? دقيقه‌اي در ديتابيس
                    insert_reconnect_marker()

            # وقفه تا بررسي بعدي
            await asyncio.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            logging.error(f"Unexpected error in monitor loop: {e}")
            await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    # اجراي حلقه اصلي asyncio
    try:
        # در ويندوز براي جلوگيري از ارورهاي Event Loop
        if platform.system() == 'Windows':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
        asyncio.run(network_monitor())
    except KeyboardInterrupt:
        print("\nWatchdog stopped by user.")
        logging.info("Network Watchdog stopped manually.")
