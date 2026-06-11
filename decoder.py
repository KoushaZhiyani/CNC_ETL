<<<<<<< HEAD
import struct
import time
from datetime import datetime
import sqlite3
import json
import copy
import queue
import threading
import requests
import logging

# ------------------------------------------------------------
# Logging setup for this module
# ------------------------------------------------------------
# Create a logger for the CNCSessionManager module
logger = logging.getLogger(__name__)
# Set default level to INFO (can be changed externally)
logger.setLevel(logging.INFO)
# If no handlers exist, add a console handler with a reasonable format
# so that log messages appear (this does not change core logic)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)


class CNCSessionManager:
    """
    Manages CNC device sessions, log processing, database storage, and board status.
    """

    def __init__(self):
        """
        Initialize the session manager:
        - board status dictionary (active sessions removed)
        - database path
        - log queue for background writing
        - device mapping from DB
        - start background DB worker thread
        """
        # active_sessions and timeout_seconds have been removed
        self.boards_status = {}  # Holds connection and log info per board

        self.db_path = r"D:\folder_project_city\CounterCNC\database_customer_club_test.db"
        self.log_queue = queue.Queue()  # Queue for batch DB inserts

        self.device_mapping = {}
        self.load_device_mappings()  # Load IP -> device_name mapping

        self._init_db()  # Ensure the WAL_DECODED table exists

        # Start the background worker that writes logs to DB in batches
        self.db_thread = threading.Thread(target=self._db_worker, daemon=True)
        self.db_thread.start()
        logger.info("CNCSessionManager initialized")

    def _init_db(self):
        """Create the WAL_DECODED table if it does not exist, with WAL journal mode."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS WAL_DECODED (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT,
                    device_name TEXT,
                    packet_id INTEGER,
                    decoded_data TEXT,
                    insert_time DATETIME,
                    is_processed INTEGER DEFAULT 0  -- Column for 8-hour processor
                )
            """)
        logger.debug("Database table WAL_DECODED ensured")

    def get_data_between_dates(self, start_date, end_date):
        """
        Retrieve raw log data from the ProductionSessions table within a date range.

        Args:
            start_date (str): Start date in 'YYYY-MM-DD' format.
            end_date (str): End date in 'YYYY-MM-DD' format.

        Returns:
            list[dict]: List of session records as dictionaries.
        """
        logger.info(f"Fetching data between {start_date} and {end_date} from ProductionSessions")
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Use row_factory to return rows as dictionaries
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Query assumes insert_time has 'YYYY-MM-DD HH:MM:SS' format
                query = """
                    SELECT SessionID, IPAddress, DeviceName, PersonnelID, PartCode, ProcessCode,
                           Quantity, Scrap, Rework, StartTime, EndTime, Status, Shift, Forms, periodic_data
                    FROM ProductionSessions 
                    WHERE date(StartTime) >= ? AND date(StartTime) <= ?
                    ORDER BY StartTime ASC
                """
                cursor.execute(query, (start_date, end_date))
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
                logger.info(f"Found {len(result)} records between {start_date} and {end_date}")
                return result
        except sqlite3.Error as e:
            logger.error(f"Database error in get_data_between_dates: {e}")
            return []

    def load_device_mappings(self):
        """Load IP-to-device_name mappings from the mapping_device_counter table."""
        db_path = r"D:\folder_project_city\CounterCNC\database_customer_club_test.db"
        logger.debug("Loading device mappings from database")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT ip, device_code FROM mapping_device_counter")
            rows = cursor.fetchall()
            for row in rows:
                db_ip = str(row[0]).strip()
                device_code = str(row[1]).strip()
                self.device_mapping[db_ip] = device_code
            logger.debug(f"Loaded {len(rows)} device mappings")
        except sqlite3.Error as e:
            logger.error(f"Error loading device mappings: {e}")
        finally:
            if 'conn' in locals() and conn:
                conn.close()

    def get_device_name(self, ip_address):
        """
        Get the human-readable device name for a given IP address.
        Falls back to IP suffix if not found in mapping.

        Args:
            ip_address (str): IP address of the device.

        Returns:
            str: Device name.
        """
        if not ip_address:
            logger.debug("get_device_name called with empty ip_address, returning 'Unknown'")
            return "Unknown"

        ip_suffix = str(ip_address).split('.')[-1]

        # Try full IP match, then suffix match
        if ip_address in self.device_mapping:
            name = self.device_mapping[ip_address]
        elif ip_suffix in self.device_mapping:
            name = self.device_mapping[ip_suffix]
        else:
            name = f"Board-{ip_suffix}"

        logger.debug(f"Device name for IP {ip_address} -> {name}")
        return name

    def process_log(self, ip_address, log_line):
        """
        Process a raw log line received from a device:
        - Parse hex packets
        - Update dashboard status
        - Queue decoded data for DB insertion
        - Handle ID 0x03 (stop packet) by sending an SMS alert.

        Args:
            ip_address (str): IP of the device.
            log_line (str): Raw log line containing hex data.
        """
        logger.info(f"Processing log from {ip_address}")
        parsed_packets = self.parse_device_hex_log(log_line)
        logger.debug(f"Parsed {len(parsed_packets)} packets from log line")

        for data in parsed_packets:
            msg_id = data["ID"]
            logger.debug(f"Handling packet ID: {hex(msg_id)}")

            # 1. Update dashboard with the last log
            self.update_board_last_log(ip_address, f"ID: {msg_id:#04x}", data)

            # 2. Prepare data and push to memory queue for raw insertion into WAL_DECODED
            device_name = self.get_device_name(ip_address)
            decoded_json = json.dumps(data)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_queue.put((str(ip_address), device_name, msg_id, decoded_json, current_time))
            logger.debug(f"Queued packet {hex(msg_id)} for DB insertion")

            # All session logic and direct insertion into ProductionSessions has been removed from here
            if msg_id == 0x03:
                # Read stored information from the current session for this board
                board_info = self.boards_status.get(ip_address, {})
                session_logs = board_info.get("session_logs", [])

                person_name = "نامشخص"
                start_time = "نامشخص"

                # Search in session logs for the start packet (0x01)
                for log_entry in session_logs:
                    if log_entry.get("ID") == 0x01:
                        # Prefer PersonnelName, fallback to Personnel code
                        person_name = log_entry.get("PersonnelName", log_entry.get("Personnel", "نامشخص"))
                        start_time = log_entry.get("Time", "نامشخص")
                        break

                end_time = datetime.now().strftime("%H:%M:%S")  # Time of receiving 0x03 as end time

                # Extract stop codes from the 0x03 packet itself
                device_stop = data.get('DeviceStopCode', 'نامشخص')
                person_stop = data.get('PersonStopCode', 'نامشخص')

                if isinstance(person_stop, (int, float)):
                    person_stop_display = f"{person_stop / 100}"
                else:
                    person_stop_display = "نامشخص"

                # Build SMS alert text
                sms_text = (
                    f"⚠️ هشدار توقف دستگاه\n"
                    f"دستگاه: {device_name}\n"
                    f"پرسنل: {person_name}\n"
                    f"زمان شروع: {start_time}\n"
                    f"زمان توقف: {end_time}\n"
                    f"کد توقف دستگاه: {device_stop}\n"
                    f"کد توقف پرسنل: {person_stop_display}\n"
                    f"واحد IT - کوشا ژیانی"
                )

                # Send SMS in a background thread to avoid blocking
                logger.info(f"Stop packet (0x03) received from {ip_address}. Sending SMS alert.")
                threading.Thread(target=self.send_sms_ir, args=(sms_text,), daemon=True).start()

    def _db_worker(self):
        """
        Background worker that takes log entries from the queue and writes them
        to the database in batches (up to 100 records) for efficiency.
        """
        logger.info("Database worker thread started")
        while True:
            batch = []
            try:
                # Wait up to 1 second for an item
                item = self.log_queue.get(timeout=1)
                batch.append(item)

                # Gather more items without blocking (up to 100 total)
                while not self.log_queue.empty() and len(batch) < 100:
                    batch.append(self.log_queue.get_nowait())

            except queue.Empty:
                continue  # No data, loop again

            if batch:
                logger.debug(f"Writing batch of {len(batch)} records to WAL_DECODED")
                try:
                    with sqlite3.connect(self.db_path, timeout=20) as conn:
                        cursor = conn.cursor()
                        # is_processed defaults to 0 automatically (not inserted)
                        cursor.executemany("""
                            INSERT INTO WAL_DECODED (ip_address, device_name, packet_id, decoded_data, insert_time)
                            VALUES (?, ?, ?, ?, ?)
                        """, batch)
                        conn.commit()
                    logger.debug(f"Batch of {len(batch)} records written successfully")
                except sqlite3.Error as e:
                    logger.error(f"Database batch insert error: {e}")
                finally:
                    # Mark each item as done to let queue.join() work if used
                    for _ in batch:
                        self.log_queue.task_done()

    def parse_device_hex_log(self, log_line):
        """
        Parse a hex log line from a CNC device and extract structured packets.

        Args:
            log_line (str): Log line possibly containing "->" separator and hex data.

        Returns:
            list[dict]: List of parsed packet dictionaries (ID and relevant fields).
        """
        logger.debug(f"Parsing hex log: {log_line[:100]}...")  # truncate for log
        # Extract hex part after "->" if present
        if "->" in log_line:
            hex_string = log_line.split("->")[1].strip()
        else:
            hex_string = log_line.strip()

        try:
            raw_bytes = bytes.fromhex(hex_string)
        except ValueError as e:
            logger.error(f"Invalid hex string: {e}")
            return []

        # Minimum packet length check
        if len(raw_bytes) < 13:
            logger.debug("Raw bytes too short, ignoring")
            return []

        parsed_data = []
        FULL_HEADER_LEN = 11

        msg_id = raw_bytes[FULL_HEADER_LEN]
        msg_len = raw_bytes[FULL_HEADER_LEN + 1]
        payload = raw_bytes[FULL_HEADER_LEN + 2 : FULL_HEADER_LEN + 2 + msg_len]

        # Packet ID 0x01: Start of session (Personnel, Part, Process)
        if msg_id == 0x01 and len(payload) >= 4:
            personnel_id = struct.unpack(">H", payload[0:2])[0]
            part_code = struct.unpack(">H", payload[2:4])[0]
            process_bytes = payload[5:].split(b'\x00')[0]
            process_code = process_bytes.decode('ascii', errors='ignore')
            personnel_name = self.get_personnel_name(personnel_id)
            part_name = self.get_part_name(part_code)

            parsed_data.append({
                "ID": 0x01,
                "Personnel": personnel_id,
                "PersonnelName": personnel_name,
                "Part": part_code,
                "PartName": part_name,
                "Process": process_code
            })
            logger.debug(f"Parsed 0x01: Personnel={personnel_id}, Part={part_code}")

        # Packet ID 0x02: Production count
        elif msg_id == 0x02 and len(payload) >= 2:
            count = struct.unpack(">H", payload[0:2])[0]
            parsed_data.append({"ID": 0x02, "Count": count})
            logger.debug(f"Parsed 0x02: Count={count}")

        # Packet ID 0x04: Scrap and Rework
        elif msg_id == 0x04 and len(payload) >= 4:
            scrap = struct.unpack(">H", payload[0:2])[0]
            rework = struct.unpack(">H", payload[2:4])[0]
            parsed_data.append({"ID": 0x04, "Scrap": scrap, "Rework": rework})
            logger.debug(f"Parsed 0x04: Scrap={scrap}, Rework={rework}")

        # Packet ID 0x05: Form data (pairs of integers)
        elif msg_id == 0x05:
            forms = []
            for i in range(0, len(payload), 4):
                if i + 4 <= len(payload):
                    f1, f2 = struct.unpack(">HH", payload[i:i+4])
                    if f1 != 0 or f2 != 0:
                        forms.append(f"{f1}/{f2}")
            parsed_data.append({"ID": 0x05, "Forms": forms})
            logger.debug(f"Parsed 0x05: Forms={forms}")

        # Packet ID 0x03: Stop codes (device and person)
        elif msg_id == 0x03 and len(payload) >= 4:
            device_stop_code, person_stop_code = struct.unpack(">HH", payload[0:4])
            parsed_data.append({"ID": 0x03, "DeviceStopCode": device_stop_code / 100, "PersonStopCode": person_stop_code})
            logger.debug(f"Parsed 0x03: DeviceStop={device_stop_code/100}, PersonStop={person_stop_code}")

        return parsed_data

    def update_board_connection(self, board_id, is_connected, ip_address=None):
        """
        Update the connection status of a board.

        Args:
            board_id (str): Identifier for the board (usually IP).
            is_connected (bool): True if connected, False otherwise.
            ip_address (str, optional): IP address of the board.
        """
        logger.info(f"Updating board {board_id} connection: {is_connected}")
        if board_id not in self.boards_status:
            self.boards_status[board_id] = {
                "ip": ip_address,
                "device_name": self.get_device_name(ip_address),
                "is_connected": False,
                "last_seen": None,
                "last_log_type": "-",
                "last_log_data": {},
                "session_logs": []
            }
            logger.debug(f"Created new board status entry for {board_id}")

        self.boards_status[board_id]["is_connected"] = is_connected
        self.boards_status[board_id]["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def update_board_last_log(self, board_id, log_type, log_data):
        """
        Update the latest log information for a board and maintain session logs.

        Args:
            board_id (str): Board identifier.
            log_type (str): Display string for the log type.
            log_data (dict): Parsed packet data.
        """
        logger.debug(f"Updating last log for board {board_id}: {log_type}")
        if board_id in self.boards_status:
            self.boards_status[board_id]["last_log_type"] = log_type
            self.boards_status[board_id]["last_log_data"] = log_data
            self.boards_status[board_id]["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            current_id = log_data.get("ID")

            # Ensure session_logs list exists
            if "session_logs" not in self.boards_status[board_id]:
                self.boards_status[board_id]["session_logs"] = []

            # If this is a start packet (0x01), reset session logs
            if current_id == 0x01:
                logger.debug(f"Board {board_id}: resetting session logs due to 0x01")
                self.boards_status[board_id]["session_logs"] = []

            # Add timestamp to the log data for display
            log_with_time = dict(log_data)
            log_with_time["Time"] = datetime.now().strftime("%H:%M:%S")

            # For scrap/rework packet (0x04), replace any existing 0x04 entry in session logs
            if current_id == 0x04:
                self.boards_status[board_id]["session_logs"] = [
                    log for log in self.boards_status[board_id]["session_logs"]
                    if log.get("ID") != 0x04
                ]

            self.boards_status[board_id]["session_logs"].append(log_with_time)
            logger.debug(f"Board {board_id} session logs now have {len(self.boards_status[board_id]['session_logs'])} entries")
        else:
            logger.warning(f"Board {board_id} not found in boards_status, cannot update last log")

    def get_all_boards_status(self):
        """Return a deep copy of the current boards' status dictionary."""
        logger.debug("Returning all boards status (deep copy)")
        return copy.deepcopy(self.boards_status)

    def get_personnel_name(self, personnel_id):
        """
        Retrieve the full name of a personnel from the users table.

        Args:
            personnel_id (int): Employee number.

        Returns:
            str: Full name or 'نامشخص' if not found.
        """
        logger.debug(f"Fetching personnel name for ID {personnel_id}")
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT fullname FROM users WHERE emp_no = ?", (personnel_id,))
                row = cursor.fetchone()
                if row:
                    name = row[0]
                    logger.debug(f"Found name: {name}")
                    return name
        except sqlite3.Error as e:
            logger.error(f"Error fetching user name for ID {personnel_id}: {e}")
        return "نامشخص"

    def get_part_name(self, part_code):
        """
        Retrieve the part name from the part_code table.

        Args:
            part_code (int): Part code number.

        Returns:
            str: Part name or 'نامشخص' if not found.
        """
        logger.debug(f"Fetching part name for code {part_code}")
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT part_name FROM part_code WHERE code = ?", (part_code,))
                row = cursor.fetchone()
                if row:
                    name = row[0]
                    logger.debug(f"Found part name: {name}")
                    return name
        except sqlite3.Error as e:
            logger.error(f"Error fetching part name for code {part_code}: {e}")
        return "نامشخص"

    def send_sms_ir(self, message):
        """
        Send an SMS using the sms.ir API.

        Args:
            message (str): SMS text content.
        """
        logger.info("Attempting to send SMS via sms.ir API")
        try:
            url = "https://api.sms.ir/v1/send/bulk"
            headers = {
                "X-API-KEY": "PBapxUHXiM0iPFlMp0r6jCXTxT7XdvDBBtoHb8T7gRA",
                "Content-Type": "application/json"
            }
            payload = {
                "lineNumber": 3000212800,
                "messageText": message,
                "mobiles": ["09394413663"],
                "sendDateTime": None
            }
            r = requests.post(url, json=payload, headers=headers, timeout=5)
            r.raise_for_status()
            logger.info(f"SMS sent successfully: {r.json()}")
        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
=======
import struct
import time
from datetime import datetime
import sqlite3
import json
import copy
import queue
import threading
import requests  

class CNCSessionManager:

    def __init__(self):
        # active_sessions و timeout_seconds حذف شدند
        self.boards_status = {} 
        
        self.db_path = r"D:\folder_project_city\CounterCNC\database_customer_club_test.db"
        self.log_queue = queue.Queue()

        self.device_mapping = {}
        self.load_device_mappings()

        self._init_db()
        
        self.db_thread = threading.Thread(target=self._db_worker, daemon=True)
        self.db_thread.start()


    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS WAL_DECODED (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT,
                    device_name TEXT,
                    packet_id INTEGER,
                    decoded_data TEXT,
                    insert_time DATETIME,
                    is_processed INTEGER DEFAULT 0  -- ستون جدید برای پردازشگر ۸ ساعته
                )
            """)



    def get_data_between_dates(self, start_date, end_date):
        """
        دریافت داده‌های لاگ خام از دیتابیس در بازه زمانی مشخص
        start_date و end_date باید با فرمت YYYY-MM-DD باشند.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # تبدیل سطرها به دیکشنری برای خروجی بهتر در اکسل
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # فرض بر این است که insert_time فرمت YYYY-MM-DD HH:MM:SS دارد
                query = """
                    SELECT SessionID, IPAddress, DeviceName, PersonnelID, PartCode, ProcessCode,  Quantity, Scrap, Rework, StartTime, EndTime, Status, Shift, Forms, periodic_data
                    FROM ProductionSessions 
                    WHERE date(StartTime) >= ? AND date(StartTime) <= ?
                    ORDER BY StartTime ASC
                """
                cursor.execute(query, (start_date, end_date))
                rows = cursor.fetchall()
                
                # تبدیل نتایج به لیست دیکشنری
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"Database error in get_data_between_dates: {e}")
            return []


    def load_device_mappings(self):
        db_path = r"D:\folder_project_city\CounterCNC\database_customer_club_test.db"
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT ip, device_code FROM mapping_device_counter")
            rows = cursor.fetchall()
            for row in rows:
                db_ip = str(row[0]).strip()
                device_code = str(row[1]).strip()
                self.device_mapping[db_ip] = device_code
        except sqlite3.Error as e:
            print(f"Error loading device mappings: {e}")
        finally:
            if 'conn' in locals() and conn:
                conn.close()

    def get_device_name(self, ip_address):
        if not ip_address:
            return "Unknown"
        
        ip_suffix = str(ip_address).split('.')[-1]
        
        if ip_address in self.device_mapping:
            return self.device_mapping[ip_address]
        elif ip_suffix in self.device_mapping:
            return self.device_mapping[ip_suffix]
        
        return f"Board-{ip_suffix}"

    def process_log(self, ip_address, log_line):
        parsed_packets = self.parse_device_hex_log(log_line)
        for data in parsed_packets:
            msg_id = data["ID"]
            
            # 1. بروزرسانی داشبورد
            self.update_board_last_log(ip_address, f"ID: {msg_id:#04x}", data)
            
            # 2. آماده‌سازی دیتا و ارسال به صف حافظه (ثبت خام در WAL)
            device_name = self.get_device_name(ip_address)
            decoded_json = json.dumps(data)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            self.log_queue.put((str(ip_address), device_name, msg_id, decoded_json, current_time))
            
            # تمام منطق سشن‌ها و درج مستقیم در ProductionSessions از اینجا حذف شد
            if msg_id == 0x03:
                # خواندن اطلاعات ذخیره شده دستگاه از سشن فعلی
                board_info = self.boards_status.get(ip_address, {})
                session_logs = board_info.get("session_logs", [])
                
                person_name = "نامشخص"
                start_time = "نامشخص"
                
                # جستجو در لاگ‌های سشن فعلی برای پیدا کردن پکت شروع (0x01)
                for log in session_logs:
                    if log.get("ID") == 0x01:
                        # اولویت با نام پرسنل است، اگر نبود کد پرسنلی را می‌گیریم
                        person_name = log.get("PersonnelName", log.get("Personnel", "نامشخص"))
                        start_time = log.get("Time", "نامشخص")
                        break

                end_time = datetime.now().strftime("%H:%M:%S") # زمان دریافت پکت 0x03 به عنوان پایان
                
                # استخراج کدهای توقف از خود پکت 0x03
                device_stop = data.get('DeviceStopCode', 'نامشخص')
                person_stop = data.get('PersonStopCode', 'نامشخص')
                
                if isinstance(person_stop, (int, float)):
                    person_stop_display = f"{person_stop / 100}"
                else:
                    person_stop_display = "نامشخص"
                
                # ساخت متن پیامک
                sms_text = (
                    f"⚠️ هشدار توقف دستگاه\n"
                    f"دستگاه: {device_name}\n"
                    f"پرسنل: {person_name}\n"
                    f"زمان شروع: {start_time}\n"
                    f"زمان توقف: {end_time}\n"
                    f"کد توقف دستگاه: {device_stop}\n"
                    f"کد توقف پرسنل: {person_stop_display}\n"
                    f"واحد IT - کوشا ژیانی"
                ) 

                threading.Thread(target=self.send_sms_ir, args=(sms_text,), daemon=True).start()



    def _db_worker(self):

        while True:
            batch = []
            try:
                item = self.log_queue.get(timeout=1)
                batch.append(item)
                
                while not self.log_queue.empty() and len(batch) < 100:
                    batch.append(self.log_queue.get_nowait())
                
            except queue.Empty:
                continue 

            if batch:
                try:
                    with sqlite3.connect(self.db_path, timeout=20) as conn:
                        cursor = conn.cursor()
                        # فیلد is_processed به صورت پیش‌فرض 0 مقداردهی می‌شود
                        cursor.executemany("""
                            INSERT INTO WAL_DECODED (ip_address, device_name, packet_id, decoded_data, insert_time)
                            VALUES (?, ?, ?, ?, ?)
                        """, batch)
                        conn.commit()
                except sqlite3.Error as e:
                    print(f"Database batch insert error: {e}")
                finally:
                    for _ in batch:
                        self.log_queue.task_done()

    def parse_device_hex_log(self, log_line):

        if "->" in log_line:
            hex_string = log_line.split("->")[1].strip()
        else:
            hex_string = log_line.strip()

        try:
            raw_bytes = bytes.fromhex(hex_string)
        except ValueError:
            return []

        if len(raw_bytes) < 13:
            return []

        parsed_data = []
        FULL_HEADER_LEN = 11
        
        msg_id = raw_bytes[FULL_HEADER_LEN]
        msg_len = raw_bytes[FULL_HEADER_LEN + 1]
        payload = raw_bytes[FULL_HEADER_LEN + 2 : FULL_HEADER_LEN + 2 + msg_len]

        if msg_id == 0x01 and len(payload) >= 4:
            personnel_id = struct.unpack(">H", payload[0:2])[0]
            part_code = struct.unpack(">H", payload[2:4])[0]
            process_bytes = payload[5:].split(b'\x00')[0]
            process_code = process_bytes.decode('ascii', errors='ignore')
            personnel_name = self.get_personnel_name(personnel_id)
            part_name = self.get_part_name(part_code)
    
            parsed_data.append({
                "ID": 0x01, 
                "Personnel": personnel_id, 
                "PersonnelName": personnel_name, 
                "Part": part_code, 
                "PartName": part_name, 
                "Process": process_code
            })


        elif msg_id == 0x02 and len(payload) >= 2:
            count = struct.unpack(">H", payload[0:2])[0]
            parsed_data.append({"ID": 0x02, "Count": count})

        elif msg_id == 0x04 and len(payload) >= 4:
            scrap = struct.unpack(">H", payload[0:2])[0]
            rework = struct.unpack(">H", payload[2:4])[0]
            parsed_data.append({"ID": 0x04, "Scrap": scrap, "Rework": rework})

        elif msg_id == 0x05:
            forms = []
            for i in range(0, len(payload), 4):
                if i + 4 <= len(payload):
                    f1, f2 = struct.unpack(">HH", payload[i:i+4])
                    if f1 != 0 or f2 != 0:
                        forms.append(f"{f1}/{f2}")
            parsed_data.append({"ID": 0x05, "Forms": forms})

        elif msg_id == 0x03 and len(payload) >= 4:
            device_stop_code, person_stop_code = struct.unpack(">HH", payload[0:4])
            parsed_data.append({"ID": 0x03, "DeviceStopCode": device_stop_code / 100, "PersonStopCode": person_stop_code})

        return parsed_data

    def update_board_connection(self, board_id, is_connected, ip_address=None):

        if board_id not in self.boards_status:
            self.boards_status[board_id] = {
                "ip": ip_address,
                "device_name": self.get_device_name(ip_address),
                "is_connected": False,
                "last_seen": None,
                "last_log_type": "-",
                "last_log_data": {},
                "session_logs": [] 
            }
        
        self.boards_status[board_id]["is_connected"] = is_connected
        self.boards_status[board_id]["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def update_board_last_log(self, board_id, log_type, log_data):

        if board_id in self.boards_status:
            self.boards_status[board_id]["last_log_type"] = log_type
            self.boards_status[board_id]["last_log_data"] = log_data
            self.boards_status[board_id]["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            current_id = log_data.get("ID")
            
            if "session_logs" not in self.boards_status[board_id]:
                self.boards_status[board_id]["session_logs"] = []

            if current_id == 0x01:
                self.boards_status[board_id]["session_logs"] = []

            log_with_time = dict(log_data)
            log_with_time["Time"] = datetime.now().strftime("%H:%M:%S")
            
            if current_id == 0x04:
                self.boards_status[board_id]["session_logs"] = [
                    log for log in self.boards_status[board_id]["session_logs"] 
                    if log.get("ID") != 0x04
                ]

            self.boards_status[board_id]["session_logs"].append(log_with_time)

    def get_all_boards_status(self):
        return copy.deepcopy(self.boards_status)


    def get_personnel_name(self, personnel_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # فرض می‌کنیم نام جدول users و ستون‌ها id و last_name است
                cursor.execute("SELECT fullname FROM users WHERE emp_no = ?", (personnel_id,))
                row = cursor.fetchone()
                if row:
                    return row[0]
        except sqlite3.Error as e:
            print(f"Error fetching user name: {e}")
        return "نامشخص"
    

    def get_part_name(self, part_code):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # نام جدول و ستون‌ها را در صورت نیاز با دیتابیس خود تطبیق دهید
                cursor.execute("SELECT part_name FROM part_code WHERE code = ?", (part_code,))
                row = cursor.fetchone()
                if row:
                    return row[0]
        except sqlite3.Error as e:
            print(f"Error fetching part name: {e}")
        return "نامشخص"



    def send_sms_ir(self, message):
        try:
            url = "https://api.sms.ir/v1/send/bulk"
            headers = {
                "X-API-KEY": "PBapxUHXiM0iPFlMp0r6jCXTxT7XdvDBBtoHb8T7gRApq9cQ",
                "Content-Type": "application/json"
            }
            payload = {
                "lineNumber": 30002128001557,
                "messageText": message,
                "mobiles": ["09394413663"],
                "sendDateTime": None
            }
            r = requests.post(url, json=payload, headers=headers, timeout=5)
            r.raise_for_status()
            print("SMS Sent Successfully:", r.json())

        except Exception as e:
            print(f"Error sending SMS: {e}")
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
