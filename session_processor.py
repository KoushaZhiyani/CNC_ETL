import sqlite3
import json
from datetime import datetime, timedelta
<<<<<<< HEAD
import logging

# ------------------------------------------------------------
# Logging setup for this module
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
# Add a console handler so that log messages appear in the terminal
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(formatter)
logging.getLogger('').addHandler(console_handler)

# ------------------------------------------------------------
# Configuration constants
# ------------------------------------------------------------
DB_PATH = r"D:\folder_project_city\CounterCNC\database_customer_club_test.db"
# Priority mapping for sorting packets: lower number = higher priority (process first)
# Packet 1 (start) gets highest priority (0), then 2, 4, 5, and finally 3 (stop)
PRIORITY_MAP = {1: 0, 2: 1, 4: 2, 5: 3, 3: 4}


def get_shift(time_obj):
    """
    Determine the work shift based on the hour of the day.

    Args:
        time_obj (datetime): The timestamp to evaluate.

    Returns:
        str: "Morning" for 06:00-15:59, "Night" for 16:00-05:59.
    """
    hour = time_obj.hour
    if 6 <= hour < 16:
        return "Morning"
    else:
        return "Night"


def apply_packet_logic(cursor, session_id, packet_id, data, insert_time_str):
    """
    Apply the logic of a specific packet (2, 3, 4, or 5) to an existing session.

    Args:
        cursor: SQLite cursor object.
        session_id (int): The ID of the production session.
        packet_id (int): Packet type (2, 3, 4, or 5).
        data (dict): Decoded packet data.
        insert_time_str (str): Timestamp when the packet was inserted (as string).
    """
    if packet_id == 2:
        # Packet 2: Production count update
=======

DB_PATH = r"D:\folder_project_city\CounterCNC\database_customer_club_test.db"
PRIORITY_MAP = {1: 0, 2: 1, 4: 2, 5: 3, 3: 4}  # اضافه شدن پکت 1 با اولويت صفر

def get_shift(time_obj):
    hour = time_obj.hour
    if 6 <= hour < 16: return "Morning"
    else: return "Night"

def apply_packet_logic(cursor, session_id, packet_id, data, insert_time_str):
    """تابع کمکي براي اعمال منطق پکت‌هاي 2, 3, 4, 5 روي يک سشن خاص"""
    if packet_id == 2:
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
        count = data.get('Count', 0)
        cursor.execute("SELECT periodic_data FROM ProductionSessions WHERE SessionID = ?", (session_id,))
        db_result = cursor.fetchone()
        try:
            periodic_list = json.loads(db_result[0]) if db_result and db_result[0] else []
        except (json.JSONDecodeError, TypeError):
            periodic_list = []
<<<<<<< HEAD

=======
            
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
        periodic_list.append(count)
        periodic_str = json.dumps(periodic_list)

        cursor.execute("""
            UPDATE ProductionSessions 
            SET Quantity = Quantity + ?, periodic_data = ?, EndTime = ? 
            WHERE SessionID = ?
        """, (count, periodic_str, insert_time_str, session_id))

    elif packet_id == 4:
<<<<<<< HEAD
        # Packet 4: Scrap and rework update
=======
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
        scrap = data.get('Scrap', 0)
        rework = data.get('Rework', 0)
        cursor.execute("""
            UPDATE ProductionSessions 
            SET Scrap = ?, Rework = ?, EndTime = ? 
            WHERE SessionID = ?
        """, (scrap, rework, insert_time_str, session_id))

    elif packet_id == 3:
<<<<<<< HEAD
        # Packet 3: Stop packet - mark session as Completed
=======
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
        cursor.execute("""
            UPDATE ProductionSessions 
            SET Status = 'Completed', EndTime = ? 
            WHERE SessionID = ?
        """, (insert_time_str, session_id))
<<<<<<< HEAD

    elif packet_id == 5:
        # Packet 5: Form data update
=======
        
    elif packet_id == 5:
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
        forms_data = data.get('Forms', [])
        forms_str = json.dumps(forms_data)
        cursor.execute("""
            UPDATE ProductionSessions 
            SET EndTime = ?, Forms = ? 
            WHERE SessionID = ?
        """, (insert_time_str, forms_str, session_id))

<<<<<<< HEAD

def process_pending_logs():
    """
    Main function to process unprocessed logs from the WAL_DECODED table.
    - Handles packet 400 as a network reconnection marker, reordering late-arriving packets.
    - Sorts packets by time and priority.
    - Updates or creates ProductionSessions records.
    - Moves orphan packets (those without an active session) into a PendingPackets table.
    - Auto-closes stale 'In Progress' sessions older than 24 hours.
    """
=======
def process_pending_logs():
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION;")
<<<<<<< HEAD

            # Create temporary table for orphan packets if it doesn't exist
=======
            
            # ايجاد جدول موقت پکت‌هاي سرگردان در صورت عدم وجود
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS PendingPackets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT,
                    packet_id INTEGER,
                    decoded_data TEXT,
                    insert_time TEXT
                )
            """)

<<<<<<< HEAD
            # Retrieve all unprocessed logs (both data packets and 400 markers)
=======
            # دريافت تمام لاگ‌هاي پردازش نشده (هم ديتا و هم 400)
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
            cursor.execute("""
                SELECT id, ip_address, device_name, packet_id, decoded_data, insert_time 
                FROM WAL_DECODED 
                WHERE is_processed = 0
            """)
            raw_logs = cursor.fetchall()
<<<<<<< HEAD

            if not raw_logs:
                conn.commit()
                logging.info("No pending logs to process.")
                return

            # Convert rows to mutable lists for easier manipulation
            logs = [list(row) for row in raw_logs]

            # Separate packet 400 (reconnection markers) from normal data packets
            p400_logs = [log for log in logs if log[3] == 400]
            data_logs = [log for log in logs if log[3] != 400]
            processed_ids = [log[0] for log in p400_logs]  # Mark packet 400 as processed

            # --- Intelligent reordering when packet 400 is present ---
            if p400_logs:
                logging.info("Packet 400 detected. Checking for delayed Packet 1 within 5 minutes...")

                # Extract and store packet 400 timestamps per IP
=======
            
            if not raw_logs:
                conn.commit() 
                return

            # تبديل به ليست براي قابليت ويرايش
            logs = [list(row) for row in raw_logs]
            
            p400_logs = [log for log in logs if log[3] == 400]
            data_logs = [log for log in logs if log[3] != 400]
            processed_ids = [log[0] for log in p400_logs] # پکت‌هاي 400 مارك پردازش مي‌خورند

            # --- منطق هوشمند جابجايي پکت‌ها در صورت وجود لاگ 400 ---
            if p400_logs:
                print("Packet 400 detected. Checking for delayed Packet 1 within 5 minutes...")
                
                # ?. استخراج و ذخيره زمان‌هاي پکت 400 براي هر IP
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
                p400_times = {}
                for p_log in p400_logs:
                    ip = p_log[1]
                    t400 = datetime.strptime(p_log[5], "%Y-%m-%d %H:%M:%S")
                    if ip not in p400_times:
                        p400_times[ip] = []
                    p400_times[ip].append(t400)

<<<<<<< HEAD
                # Preliminary sort by time to find ordering anomalies
                data_logs.sort(key=lambda x: x[5])

                ips = set(log[1] for log in data_logs)
                for ip in ips:
                    # Skip if this IP has no packet 400
=======
                # مرتب‌سازي اوليه صرفاً بر اساس زمان براي پيدا کردن تاخيرها
                data_logs.sort(key=lambda x: x[5])
                
                ips = set(log[1] for log in data_logs)
                for ip in ips:
                    # اگر اين IP قطعي (پکت 400) نداشته، از آن مي‌گذريم
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
                    if ip not in p400_times:
                        continue

                    ip_logs = [log for log in data_logs if log[1] == ip]
                    for i in range(len(ip_logs)):
<<<<<<< HEAD
                        if ip_logs[i][3] == 2:  # Found a packet 2
                            t2 = datetime.strptime(ip_logs[i][5], "%Y-%m-%d %H:%M:%S")

                            # Check if this packet 2 falls within 5 minutes (300 seconds) after any packet 400
                            is_in_window = False
                            for t400 in p400_times[ip]:
                                diff_from_400 = (t2 - t400).total_seconds()
                                if 0 <= diff_from_400 <= 300:
                                    is_in_window = True
                                    break

                            if not is_in_window:
                                continue  # Not within window – no reordering needed

                            # Search forward for a packet 1 belonging to the same IP
                            for j in range(i + 1, len(ip_logs)):
                                if ip_logs[j][3] == 1:
                                    t1 = datetime.strptime(ip_logs[j][5], "%Y-%m-%d %H:%M:%S")
                                    diff_seconds = (t1 - t2).total_seconds()

                                    # If packet 1 arrived less than 60 seconds after packet 2, reorder
                                    if 0 <= diff_seconds <= 60:
                                        logging.info(f"Fixing order for IP {ip}: Moving Packet 1 before Packet 2.")
                                        # Adjust packet 1 timestamp to 1 second before packet 2
                                        new_t1 = (t2 - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")

                                        # Apply the new timestamp to the original data_logs list
=======
                        if ip_logs[i][3] == 2: # پيدا کردن پکت 2
                            t2 = datetime.strptime(ip_logs[i][5], "%Y-%m-%d %H:%M:%S")
                            
                            # ?. بررسي اينکه آيا اين پکت 2 در پنجره 5 دقيقه‌اي (300 ثانيه‌اي) پس از لاگ 400 قرار دارد؟
                            is_in_window = False
                            for t400 in p400_times[ip]:
                                diff_from_400 = (t2 - t400).total_seconds()
                                if 0 <= diff_from_400 <= 300: # بين 0 تا 300 ثانيه
                                    is_in_window = True
                                    break
                            
                            if not is_in_window:
                                continue # اگر خارج از بازه 5 دقيقه بود، جابجايي انجام نمي‌شود
                            
                            # ?. جستجو به جلو براي پيدا کردن پکت 1 متعلق به همين IP
                            for j in range(i+1, len(ip_logs)):
                                if ip_logs[j][3] == 1:
                                    t1 = datetime.strptime(ip_logs[j][5], "%Y-%m-%d %H:%M:%S")
                                    diff_seconds = (t1 - t2).total_seconds()
                                    
                                    # اگر پکت 1 در کمتر از 60 ثانيه بعد از پکت 2 آمده باشد
                                    if 0 <= diff_seconds <= 60:
                                        print(f"Fixing order for IP {ip}: Moving Packet 1 before Packet 2.")
                                        # زمان پکت 1 را به يک ثانيه قبل از پکت 2 تغيير مي‌دهيم تا سورتينگ اصلي درست کار کند
                                        new_t1 = (t2 - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
                                        
                                        # اعمال زمان جديد روي ليست اصلي ديتا
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
                                        for m_log in data_logs:
                                            if m_log[0] == ip_logs[j][0]:
                                                m_log[5] = new_t1
                                                break
<<<<<<< HEAD
                                        break  # Exit the inner search loop after fixing

            # --- Final sorting workflow ---
            # Sort data_logs by insert_time, then by priority (lowest priority number first)
            data_logs.sort(key=lambda x: (x[5], PRIORITY_MAP.get(x[3], 99)))

            # Process each data log in order
=======
                                        break # پس از اصلاح، حلقه جستجوي پکت 1 را مي‌شکنيم

            # --- Sorting Workflow اصلي ---
            # حالا مرتب‌سازي نهايي را اعمال مي‌کنيم. با تغيير زمان بالا، پکت 1 دقيقاً قبل از 2 قرار مي‌گيرد.
            data_logs.sort(key=lambda x: (x[5], PRIORITY_MAP.get(x[3], 99)))

>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
            for log in data_logs:
                log_id, ip_address, device_name, packet_id, decoded_data, insert_time_str = log
                data = json.loads(decoded_data)
                log_time = datetime.strptime(insert_time_str, "%Y-%m-%d %H:%M:%S")
                processed_ids.append(log_id)
<<<<<<< HEAD

                # Find the latest session for this IP
=======
                
                # پيدا کردن آخرين سشن
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
                cursor.execute("""
                    SELECT SessionID, Status FROM ProductionSessions 
                    WHERE IPAddress = ? 
                    ORDER BY SessionID DESC LIMIT 1
                """, (ip_address,))
                latest_session = cursor.fetchone()
<<<<<<< HEAD

                is_active = latest_session and latest_session[1] == 'In Progress'

                if packet_id == 1:
                    # Packet 1: Start a new session
                    # Close the previous session if it is still active
=======
                
                is_active = latest_session and latest_session[1] == 'In Progress'

                if packet_id == 1:
                    # بستن سشن قبلي اگر باز است
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
                    if is_active:
                        cursor.execute("""
                            UPDATE ProductionSessions 
                            SET Status = 'Completed', EndTime = ? 
                            WHERE SessionID = ?
                        """, (insert_time_str, latest_session[0]))
<<<<<<< HEAD

                    # Create a new session
=======
                    
                    # ساخت سشن جديد
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
                    shift = get_shift(log_time)
                    cursor.execute("""
                        INSERT INTO ProductionSessions 
                        (IPAddress, DeviceName, PersonnelID, PartCode, ProcessCode, Quantity, Scrap, Rework, StartTime, EndTime, Status, Shift)
                        VALUES (?, ?, ?, ?, ?, 0, 0, 0, ?, ?, 'In Progress', ?)
<<<<<<< HEAD
                    """, (ip_address, device_name, data.get('Personnel', ''), data.get('Part', ''),
                          data.get('Process', ''), insert_time_str, insert_time_str, shift))

                    new_session_id = cursor.lastrowid

                    # --- Apply any orphan packets that were pending for this IP ---
                    cursor.execute("SELECT id, packet_id, decoded_data, insert_time FROM PendingPackets WHERE ip_address = ?", (ip_address,))
                    pending = cursor.fetchall()

                    if pending:
                        # Sort pending packets by priority (2 -> 4 -> 5 -> 3)
                        pending_sorted = sorted(pending, key=lambda x: PRIORITY_MAP.get(x[1], 99))

=======
                    """, (ip_address, device_name, data.get('Personnel', ''), data.get('Part', ''), data.get('Process', ''), insert_time_str, insert_time_str, shift))
                    
                    new_session_id = cursor.lastrowid

                    # --- اعمال پکت‌هاي سرگردان (Orphan Packets) ---
                    cursor.execute("SELECT id, packet_id, decoded_data, insert_time FROM PendingPackets WHERE ip_address = ?", (ip_address,))
                    pending = cursor.fetchall()
                    
                    if pending:
                        # مرتب‌سازي پکت‌هاي سرگردان بر اساس منطق 2 -> 4 -> 5 -> 3
                        pending_sorted = sorted(pending, key=lambda x: PRIORITY_MAP.get(x[1], 99))
                        
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
                        for p_row in pending_sorted:
                            p_db_id, p_id, p_raw, p_time = p_row
                            p_data = json.loads(p_raw)
                            apply_packet_logic(cursor, new_session_id, p_id, p_data, p_time)
<<<<<<< HEAD

                        # Clear the processed pending packets
                        cursor.execute("DELETE FROM PendingPackets WHERE ip_address = ?", (ip_address,))

                else:
                    # Packet is 2, 3, 4, or 5 (not a start packet)
                    if is_active:
                        # If there is an active session, apply directly
                        apply_packet_logic(cursor, latest_session[0], packet_id, data, insert_time_str)
                    else:
                        # No active session: handle orphan packets
                        if packet_id == 3:
                            # Packet 3 arrived without an active session
=======
                            
                        # پاک‌سازي پکت‌هاي استفاده شده
                        cursor.execute("DELETE FROM PendingPackets WHERE ip_address = ?", (ip_address,))
                else:
                    # اگر پکت 1 نيست (2, 3, 4, يا 5)
                    if is_active:
                        # اگر سشن فعال است مستقيماً اعمال کن
                        apply_packet_logic(cursor, latest_session[0], packet_id, data, insert_time_str)
                    else:
                        # اگر سشن فعال نداريم:
                        # - پکت‌هاي 2/4/5 فقط pending شوند
                        # - وقتي پکت 3 رسيد، اگر pending براي اين IP وجود داشت
                        #   همه pendingها + خود پکت 3 داخل يک سشن ناشناس اعمال شوند

                        if packet_id == 3:
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
                            cursor.execute("""
                                SELECT id, packet_id, decoded_data, insert_time
                                FROM PendingPackets
                                WHERE ip_address = ?
                            """, (ip_address,))
                            pending = cursor.fetchall()

                            if pending:
<<<<<<< HEAD
                                # Create an anonymous session for all pending packets + this packet 3
=======
                                # ساخت سشن ناشناس
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
                                shift = get_shift(log_time)
                                cursor.execute("""
                                    INSERT INTO ProductionSessions
                                    (IPAddress, DeviceName, PersonnelID, PartCode, ProcessCode,
                                     Quantity, Scrap, Rework, StartTime, EndTime, Status, Shift)
                                    VALUES (?, ?, ?, ?, ?, 0, 0, 0, ?, ?, 'In Progress', ?)
                                """, (
                                    ip_address,
                                    device_name,
                                    'UNKNOWN',
                                    'UNKNOWN',
                                    'UNKNOWN',
                                    insert_time_str,
                                    insert_time_str,
                                    shift
                                ))

                                new_session_id = cursor.lastrowid

<<<<<<< HEAD
                                # Combine pending packets and this packet 3, then sort by time and priority
                                all_packets = list(pending) + [(None, packet_id, decoded_data, insert_time_str)]
=======
                                # همه pendingها + خود packet 3
                                all_packets = list(pending) + [(None, packet_id, decoded_data, insert_time_str)]

                                # مرتب‌سازي بر اساس زمان و بعد اولويت
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
                                all_packets_sorted = sorted(
                                    all_packets,
                                    key=lambda x: (x[3], PRIORITY_MAP.get(x[1], 99))
                                )

                                for p_row in all_packets_sorted:
                                    _, p_id, p_raw, p_time = p_row
                                    p_data = json.loads(p_raw)
                                    apply_packet_logic(cursor, new_session_id, p_id, p_data, p_time)

<<<<<<< HEAD
                                # Clear pending packets for this IP
                                cursor.execute("DELETE FROM PendingPackets WHERE ip_address = ?", (ip_address,))
                            else:
                                # No pending packets – store this packet 3 as pending
=======
                                # پاک‌سازي pendingهاي اين IP
                                cursor.execute("DELETE FROM PendingPackets WHERE ip_address = ?", (ip_address,))
                            else:
                                # اگر packet 3 آمد ولي pending نداشت، خودش هم pending شود
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
                                cursor.execute("""
                                    INSERT INTO PendingPackets (ip_address, packet_id, decoded_data, insert_time)
                                    VALUES (?, ?, ?, ?)
                                """, (ip_address, packet_id, decoded_data, insert_time_str))
                        else:
<<<<<<< HEAD
                            # Packets 2, 4, or 5 without an active session: store in pending table
=======
                            # packet هاي 2 / 4 / 5
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
                            cursor.execute("""
                                INSERT INTO PendingPackets (ip_address, packet_id, decoded_data, insert_time)
                                VALUES (?, ?, ?, ?)
                            """, (ip_address, packet_id, decoded_data, insert_time_str))

<<<<<<< HEAD
            # Mark all successfully processed logs as processed
            if processed_ids:
                cursor.executemany("UPDATE WAL_DECODED SET is_processed = 1 WHERE id = ?", [(pid,) for pid in processed_ids])

            # Auto-close any 'In Progress' sessions older than 24 hours
=======
            if processed_ids:
                cursor.executemany("UPDATE WAL_DECODED SET is_processed = 1 WHERE id = ?", [(pid,) for pid in processed_ids])

>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
            cursor.execute("""
                UPDATE ProductionSessions 
                SET Status = 'Auto-Closed' 
                WHERE Status = 'In Progress' 
                AND EndTime < datetime('now', 'localtime', '-24 hours')
            """)
<<<<<<< HEAD

            conn.commit()
            logging.info(f"{len(processed_ids)} logs processed successfully.")

    except sqlite3.Error as e:
        logging.error(f"Database processing error: {e}")


# Run the main processing function
if __name__ == "__main__":
    process_pending_logs()
=======
                
            conn.commit()
            print(f"{len(processed_ids)} logs processed successfully.")

    except sqlite3.Error as e:
        print(f"Database processing error: {e}")

process_pending_logs()
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
