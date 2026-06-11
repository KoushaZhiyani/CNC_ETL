import asyncio
import sys
import time
import logging
from typing import Set
import ctypes
from ctypes import wintypes
import threading
from collections import Counter 

from decoder import CNCSessionManager 
from dashboard import run_flask_dashboard 

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout
)


class Server:
    BUFFER_SIZE = 256
    PORT = 100
    CHECK_INTERVAL = 1.0

    def __init__(self):
        # ********* IP دستی اینجا قرار می‌گیرد *********
        # مثال: "192.168.1.10"
        self.host = "192.168.1.3"
        # **********************************************

        self.port = self.PORT
        self.clients: Set[asyncio.StreamWriter] = set()
        self.lock = asyncio.Lock()
        self.server = None
        self.checker_task = None
        self.exit_event = asyncio.Event()

        self.ip_connections = Counter()



    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        ip = addr[0]

        logging.info(
            f"Client Connected Time: {time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"Number of Connected Clients: {len(self.clients) + 1} IP: {addr[0]}:{addr[1]}"
        )

        async with self.lock:
            self.clients.add(writer)
            self.ip_connections[ip] += 1
            # فقط اگر اولین کانکشن این IP است وضعیت را آنلاین کن
            if self.ip_connections[ip] == 1:
                session_manager.update_board_connection(ip, True, ip)

        client_buffer = bytearray()
        MAGIC_HEADER = bytes.fromhex("4500") 
        FULL_HEADER_LEN = 11

        try:
            while not self.exit_event.is_set():
                try:
                    data = await asyncio.wait_for(reader.read(self.BUFFER_SIZE), timeout=2.0)
                except asyncio.TimeoutError:
                    continue
                except asyncio.IncompleteReadError:
                    break

                if not data:
                    break

                # اضافه کردن دیتای جدید به بافر کلاینت
                client_buffer.extend(data)

                # پردازش بافر تا زمانی که پکت کامل در آن وجود دارد
                while True:
                    idx = client_buffer.find(MAGIC_HEADER)
                    
                    if idx == -1:
                        # اگر هدر پیدا نشد، اما ممکن است بخشی از هدر در انتهای بافر باشد
                        # به اندازه (طول کل هدر - 1) بایت آخر را نگه می‌داریم تا مموری پر نشود
                        if len(client_buffer) > FULL_HEADER_LEN:
                            client_buffer = client_buffer[-(FULL_HEADER_LEN-1):]
                        break

                    # هدر پیدا شد. بررسی می‌کنیم آیا بایت Length دریافت شده است یا خیر 
                    # (طول کل هدر + 1 بایت ID + 1 بایت Length = FULL_HEADER_LEN + 2)
                    if len(client_buffer) < idx + FULL_HEADER_LEN + 2:
                        break # صبر می‌کنیم تا دیتای بیشتری بیاید

                    # استخراج طول پیام از بایتی که بعد از هدر و ID قرار دارد
                    msg_len = client_buffer[idx + FULL_HEADER_LEN + 1]
                    total_packet_size = FULL_HEADER_LEN + 2 + msg_len

                    # آیا کل پکت (هدر + طول متغیر) دریافت شده است؟
                    if len(client_buffer) < idx + total_packet_size:
                        break # صبر می‌کنیم تا بقیه پکت بیاید

                    # استخراج یک پکت کامل و سالم
                    full_packet = client_buffer[idx : idx + total_packet_size]
                    
                    # تبدیل پکت کامل به هگز و ارسال به پردازشگر
                    hex_data = " ".join(f"{b:02X}" for b in full_packet)
                    
                    session_manager.process_log(ip, hex_data)
                    logging.info(f"RX {addr[0]}:{addr[1]} -> {hex_data}")

                    # حذف پکت پردازش شده از بافر
                    client_buffer = client_buffer[idx + total_packet_size:]

        except (ConnectionError, OSError):
            pass

        finally:
            logging.info(f"Client Disconnected: {addr}")
            async with self.lock:
                self.clients.discard(writer)
                self.ip_connections[ip] -= 1
                
                # اگر هیچ کانکشن زنده‌ای از این IP باقی نمانده بود، آفلاینش کن
                if self.ip_connections[ip] <= 0:
                    self.ip_connections[ip] = 0
                    session_manager.update_board_connection(ip, False, ip)
            
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass


    async def connection_checker(self):
        while not self.exit_event.is_set():
            await asyncio.sleep(self.CHECK_INTERVAL)

            # session_manager.check_timeouts() 
            async with self.lock:
                clients = list(self.clients)

            for writer in clients:
                try:
                    writer.write(b'\x00')
                    await asyncio.wait_for(writer.drain(), timeout=2.0)
                except:
                    addr = writer.get_extra_info("peername")
                    ip = addr[0] # گرفتن IP کلاینت قطع شده
                    logging.warning(f"Dead client removed: {addr}")
                    async with self.lock:
                        self.clients.discard(writer)
                        # --- بخش اضافه شده برای آپدیت وضعیت ---
                        self.ip_connections[ip] -= 1
                        if self.ip_connections[ip] <= 0:
                            self.ip_connections[ip] = 0
                            session_manager.update_board_connection(ip, False, ip)
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except:
                        pass

    async def start(self):
        print("Rizan Felez Datalogger V1.1 Server")
        print("Loading Data ...")
        print("Checking System ...")

        if sys.platform == "win32":
            ctypes.windll.kernel32.SetConsoleTitleW("Server")
            self._register_console_handler()

        logging.info(f"Starting server on {self.host}:{self.port} ...")

        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )

        self.checker_task = asyncio.create_task(self.connection_checker())

        async with self.server:
            await self.exit_event.wait()

    def _register_console_handler(self):
        def console_handler(event_type):
            if event_type == 2:
                logging.info("X button clicked. Shutting down...")
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(self.shutdown)
            return False

        ConsoleEventDelegate = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int)
        self._handler_ref = ConsoleEventDelegate(console_handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(self._handler_ref, True)

    def shutdown(self):
        if not self.exit_event.is_set():
            self.exit_event.set()
            if self.checker_task:
                self.checker_task.cancel()
            if self.server:
                self.server.close()

    async def cleanup(self):
        async with self.lock:
            for writer in list(self.clients):
                try:
                    writer.close()
                    await writer.wait_closed()
                except:
                    pass
            self.clients.clear()

        if self.server:
            self.server.close()
            await self.server.wait_closed()

        logging.info("Server shutdown complete.")




async def main():
    server_instance = Server()
    try:
        await server_instance.start()
    finally:
        await server_instance.cleanup()

if __name__ == '__main__':
    session_manager = CNCSessionManager()

    # اجرای Flask در یک Thread کاملاً مجزا
    flask_thread = threading.Thread(
        target=run_flask_dashboard, 
        args=(session_manager,), 
        daemon=True
    )
    flask_thread.start()

    # اجرای سرور اصلی asyncio (TCP)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped via KeyboardInterrupt.")
