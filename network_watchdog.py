import asyncio
import sqlite3
import logging
import platform
from datetime import datetime

# ==========================================
# Configuration
# ==========================================
DB_PATH = r"D:\folder_project_city\CounterCNC\database_customer_club_test.db"

# List of CNC board IP addresses (example: 37 devices)
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

CHECK_INTERVAL = 5  # Seconds between network checks

# Thresholds for network state detection (tolerant of a few offline devices)
# If at least this many boards are down, consider the network as offline
MIN_DOWN_TO_CONSIDER_OFFLINE = len(BOARD_IPS) - 8
# If at least this many boards are up, consider the network as back online
MIN_UP_TO_CONSIDER_ONLINE = len(BOARD_IPS) - 10

# Logger configuration
logging.basicConfig(
    filename='network_watchdog.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ==========================================
# Helper Functions
# ==========================================
async def ping_ip(ip):
    """
    Asynchronously ping an IP address.
    Returns True if the ping succeeds, False otherwise.

    Args:
        ip (str): The IP address to ping.

    Returns:
        bool: True if reachable, False otherwise.
    """
    # Use '-n' on Windows, '-c' on Linux/macOS
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    
    # Run ping command with a timeout of 1 second, suppress output
    process = await asyncio.create_subprocess_exec(
        'ping', param, '1', '-w', '1000', ip,  # Timeout = 1000ms
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await process.wait()
    return process.returncode == 0

def insert_reconnect_marker():
    """
    Insert packet 400 into the WAL_DECODED table as a network reconnection signal.
    This acts as a jitter buffer trigger for downstream processors.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Use datetime('now', 'localtime') to get Windows local time accurately
            cursor.execute("""
                INSERT INTO WAL_DECODED (packet_id, decoded_data, insert_time) 
                VALUES (400, '{"event": "network_reconnected", "source": "watchdog"}', datetime('now', 'localtime'))
            """)
            conn.commit()
            logging.info("Packet 400 (Reconnect Marker) successfully inserted into database.")
    except Exception as e:
        logging.error(f"Failed to insert Packet 400 into database: {e}")

# ==========================================
# Main Monitoring Logic
# ==========================================
async def network_monitor():
    """
    Main asynchronous monitoring loop.
    Periodically pings all configured IPs, tracks network state (online/offline),
    and inserts a reconnect marker when the network comes back online.
    """
    logging.info("Network Watchdog started. Monitoring 37 CNC boards...")
    
    # For now, I'll implement the function as follows (assuming console handler already added).
    logging.info("Watchdog is running... (Press Ctrl+C to stop)")  # Replaces print
    
    # Initially assume network is up (so we detect the first down event)
    is_network_down = False 
    
    while True:
        try:
            # Ping all IPs concurrently (execution time ≈ slowest ping, not sum)
            ping_tasks = [ping_ip(ip) for ip in BOARD_IPS]
            results = await asyncio.gather(*ping_tasks)
            
            up_count = sum(results)
            down_count = len(BOARD_IPS) - up_count
            
            # 1. Detect network down
            if down_count >= MIN_DOWN_TO_CONSIDER_OFFLINE:
                if not is_network_down:
                    is_network_down = True
                    logging.warning(f"NETWORK DOWN DETECTED! {down_count}/{len(BOARD_IPS)} boards are unreachable.")
                    # Also log to console via warning level (console handler will show it)
            
            # 2. Detect network reconnection
            elif up_count >= MIN_UP_TO_CONSIDER_ONLINE:
                if is_network_down:
                    is_network_down = False
                    logging.info(f"NETWORK RECONNECTED! {up_count}/{len(BOARD_IPS)} boards are back online.")
                    
                    # Insert the jitter buffer trigger into the database
                    insert_reconnect_marker()
            
            # Wait until the next check
            await asyncio.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            logging.error(f"Unexpected error in monitor loop: {e}")
            await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    # Add a console handler so that log messages appear in the terminal
    # (this replaces the original print statements while adhering to logging-only rule)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(formatter)
    logging.getLogger('').addHandler(console_handler)
    
    # Run the main asyncio loop
    try:
        # On Windows, use ProactorEventLoopPolicy to avoid event loop issues
        if platform.system() == 'Windows':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
        asyncio.run(network_monitor())
    except KeyboardInterrupt:
        print("\nWatchdog stopped by user.")  # This print is for immediate user feedback; we also log it.
        logging.info("Network Watchdog stopped manually.")