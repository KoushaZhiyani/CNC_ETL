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

    # def process_log(self, ip_address, log_line):
    #     parsed_packets = self.parse_device_hex_log(log_line)
    #     for data in parsed_packets:
    #         msg_id = data["ID"]
            
    #         # 1. بروزرسانی داشبورد
    #         self.update_board_last_log(ip_address, f"ID: {msg_id:#04x}", data)
            
    #         # 2. آماده‌سازی دیتا و ارسال به صف حافظه (ثبت خام در WAL)
    #         device_name = self.get_device_name(ip_address)
    #         decoded_json = json.dumps(data)
    #         current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
    #         self.log_queue.put((str(ip_address), device_name, msg_id, decoded_json, current_time))
            
    #         # تمام منطق سشن‌ها و درج مستقیم در ProductionSessions از اینجا حذف شد
    #         if msg_id == 0x03:
    #             # خواندن اطلاعات ذخیره شده دستگاه از سشن فعلی
    #             board_info = self.boards_status.get(ip_address, {})
    #             session_logs = board_info.get("session_logs", [])
                
    #             person_name = "نامشخص"
    #             start_time = "نامشخص"
                
    #             # جستجو در لاگ‌های سشن فعلی برای پیدا کردن پکت شروع (0x01)
    #             for log in session_logs:
    #                 if log.get("ID") == 0x01:
    #                     # اولویت با نام پرسنل است، اگر نبود کد پرسنلی را می‌گیریم
    #                     person_name = log.get("PersonnelName", log.get("Personnel", "نامشخص"))
    #                     start_time = log.get("Time", "نامشخص")
    #                     break

    #             end_time = datetime.now().strftime("%H:%M:%S") # زمان دریافت پکت 0x03 به عنوان پایان
                
    #             # استخراج کدهای توقف از خود پکت 0x03
    #             device_stop = data.get('DeviceStopCode', 'نامشخص')
    #             person_stop = data.get('PersonStopCode', 'نامشخص')
                
    #             if isinstance(person_stop, (int, float)):
    #                 person_stop_display = f"{person_stop / 100}"
    #             else:
    #                 person_stop_display = "نامشخص"
                
    #             # ساخت متن پیامک
    #             sms_text = (
    #                 f"⚠️ هشدار توقف دستگاه\n"
    #                 f"دستگاه: {device_name}\n"
    #                 f"پرسنل: {person_name}\n"
    #                 f"زمان شروع: {start_time}\n"
    #                 f"زمان توقف: {end_time}\n"
    #                 f"کد توقف دستگاه: {device_stop}\n"
    #                 f"کد توقف پرسنل: {person_stop_display}\n"
    #                 f"واحد IT - کوشا ژیانی"
    #             ) 

    #             threading.Thread(target=self.send_sms_ir, args=(sms_text,), daemon=True).start()


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
