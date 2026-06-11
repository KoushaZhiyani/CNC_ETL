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

<<<<<<< HEAD
# Configure logging for the entire module
=======
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout
)


class Server:
<<<<<<< HEAD
    """
    Asyncio TCP server that listens for CNC device connections,
    receives raw binary data, extracts packets, and forwards decoded
    information to the CNCSessionManager.
    """
    BUFFER_SIZE = 256
    PORT = 100
    CHECK_INTERVAL = 1.0  # Interval (seconds) for connection health checks

    def __init__(self):
        # ********* Manual IP address is set here *********
        # Example: "192.168.1.10"
=======
    BUFFER_SIZE = 256
    PORT = 100
    CHECK_INTERVAL = 1.0

    def __init__(self):
        # ********* IP دستی اینجا قرار می‌گیرد *********
        # مثال: "192.168.1.10"
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
        self.host = "192.168.1.3"
        # **********************************************

        self.port = self.PORT
<<<<<<< HEAD
        self.clients: Set[asyncio.StreamWriter] = set()  # Active client writers
        self.lock = asyncio.Lock()                      # Protect shared client set
        self.server = None
        self.checker_task = None
        self.exit_event = asyncio.Event()               # Signal for graceful shutdown

        self.ip_connections = Counter()                 # Track active connections per IP


    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Handle an individual client connection:
        - Read data chunks
        - Buffer and parse packets using magic header 0x4500
        - Forward valid packets to the session manager
        - Update connection status on connect/disconnect
        """
=======
        self.clients: Set[asyncio.StreamWriter] = set()
        self.lock = asyncio.Lock()
        self.server = None
        self.checker_task = None
        self.exit_event = asyncio.Event()

        self.ip_connections = Counter()



    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
        addr = writer.get_extra_info("peername")
        ip = addr[0]

        logging.info(
            f"Client Connected Time: {time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"Number of Connected Clients: {len(self.clients) + 1} IP: {addr[0]}:{addr[1]}"
        )

<<<<<<< HEAD
        # Add this client to the shared set and update connection counter
        async with self.lock:
            self.clients.add(writer)
            self.ip_connections[ip] += 1
            # Only mark the board as online if this is the first connection from this IP
=======
        async with self.lock:
            self.clients.add(writer)
            self.ip_connections[ip] += 1
            # فقط اگر اولین کانکشن این IP است وضعیت را آنلاین کن
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
            if self.ip_connections[ip] == 1:
                session_manager.update_board_connection(ip, True, ip)

        client_buffer = bytearray()
<<<<<<< HEAD
        MAGIC_HEADER = bytes.fromhex("4500")   # Packet start marker
        FULL_HEADER_LEN = 11                   # Length of header before variable payload
=======
        MAGIC_HEADER = bytes.fromhex("4500") 
        FULL_HEADER_LEN = 11
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487

        try:
            while not self.exit_event.is_set():
                try:
<<<<<<< HEAD
                    # Read up to BUFFER_SIZE bytes with a timeout to allow periodic checks
                    data = await asyncio.wait_for(reader.read(self.BUFFER_SIZE), timeout=2.0)
                except asyncio.TimeoutError:
                    continue  # No data received, loop again
                except asyncio.IncompleteReadError:
                    break      # Connection closed

                if not data:
                    break      # No more data, client disconnected

                # Append new data to the client's buffer
                client_buffer.extend(data)

                # Process the buffer as long as complete packets are present
=======
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
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
                while True:
                    idx = client_buffer.find(MAGIC_HEADER)
                    
                    if idx == -1:
<<<<<<< HEAD
                        # Header not found; keep only the last (FULL_HEADER_LEN-1) bytes
                        # to avoid memory bloat while preserving a possible partial header
=======
                        # اگر هدر پیدا نشد، اما ممکن است بخشی از هدر در انتهای بافر باشد
                        # به اندازه (طول کل هدر - 1) بایت آخر را نگه می‌داریم تا مموری پر نشود
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
                        if len(client_buffer) > FULL_HEADER_LEN:
                            client_buffer = client_buffer[-(FULL_HEADER_LEN-1):]
                        break

<<<<<<< HEAD
                    # Check if we have enough bytes to read the length field
                    # (header + ID byte + length byte = FULL_HEADER_LEN + 2)
                    if len(client_buffer) < idx + FULL_HEADER_LEN + 2:
                        break  # Wait for more data

                    # Extract message length from the byte after header+ID
                    msg_len = client_buffer[idx + FULL_HEADER_LEN + 1]
                    total_packet_size = FULL_HEADER_LEN + 2 + msg_len

                    # Check if the entire packet (header + variable part) is available
                    if len(client_buffer) < idx + total_packet_size:
                        break  # Wait for the rest of the packet

                    # Extract one complete packet
                    full_packet = client_buffer[idx : idx + total_packet_size]
                    
                    # Convert packet bytes to hex string for logging and processing
                    hex_data = " ".join(f"{b:02X}" for b in full_packet)
                    
                    # Send the decoded hex line to the session manager
                    session_manager.process_log(ip, hex_data)
                    logging.info(f"RX {addr[0]}:{addr[1]} -> {hex_data}")

                    # Remove the processed packet from the buffer
                    client_buffer = client_buffer[idx + total_packet_size:]

        except (ConnectionError, OSError):
            # Network errors are handled in the finally block
=======
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
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
            pass

        finally:
            logging.info(f"Client Disconnected: {addr}")
            async with self.lock:
                self.clients.discard(writer)
                self.ip_connections[ip] -= 1
                
<<<<<<< HEAD
                # If no more active connections from this IP, mark board as offline
=======
                # اگر هیچ کانکشن زنده‌ای از این IP باقی نمانده بود، آفلاینش کن
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
                if self.ip_connections[ip] <= 0:
                    self.ip_connections[ip] = 0
                    session_manager.update_board_connection(ip, False, ip)
            
<<<<<<< HEAD
            # Clean up the writer
=======
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass


    async def connection_checker(self):
<<<<<<< HEAD
        """
        Periodically check all connected clients by sending a null byte.
        If the write fails, remove the dead client and update connection status.
        """
        while not self.exit_event.is_set():
            await asyncio.sleep(self.CHECK_INTERVAL)

            # session_manager.check_timeouts()  # (commented out, originally)
=======
        while not self.exit_event.is_set():
            await asyncio.sleep(self.CHECK_INTERVAL)

            # session_manager.check_timeouts() 
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
            async with self.lock:
                clients = list(self.clients)

            for writer in clients:
                try:
<<<<<<< HEAD
                    # Send a keep-alive null byte
                    writer.write(b'\x00')
                    await asyncio.wait_for(writer.drain(), timeout=2.0)
                except Exception:
                    addr = writer.get_extra_info("peername")
                    ip = addr[0]  # Extract IP of the dead client
                    logging.warning(f"Dead client removed: {addr}")
                    async with self.lock:
                        self.clients.discard(writer)
                        # Update connection counter and board status
=======
                    writer.write(b'\x00')
                    await asyncio.wait_for(writer.drain(), timeout=2.0)
                except:
                    addr = writer.get_extra_info("peername")
                    ip = addr[0] # گرفتن IP کلاینت قطع شده
                    logging.warning(f"Dead client removed: {addr}")
                    async with self.lock:
                        self.clients.discard(writer)
                        # --- بخش اضافه شده برای آپدیت وضعیت ---
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
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
<<<<<<< HEAD
        """Start the TCP server, connection checker task, and wait for shutdown signal."""
        logging.info("Rizan Felez Datalogger V1.1 Server")
        logging.info("Loading Data ...")
        logging.info("Checking System ...")

        if sys.platform == "win32":
            # Set console title and register handler for Ctrl+C / window close
=======
        print("Rizan Felez Datalogger V1.1 Server")
        print("Loading Data ...")
        print("Checking System ...")

        if sys.platform == "win32":
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
            ctypes.windll.kernel32.SetConsoleTitleW("Server")
            self._register_console_handler()

        logging.info(f"Starting server on {self.host}:{self.port} ...")

<<<<<<< HEAD
        # Create and start the asyncio server
=======
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )

<<<<<<< HEAD
        # Start the background connection health checker
        self.checker_task = asyncio.create_task(self.connection_checker())

        # Run the server until exit_event is set
=======
        self.checker_task = asyncio.create_task(self.connection_checker())

>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
        async with self.server:
            await self.exit_event.wait()

    def _register_console_handler(self):
<<<<<<< HEAD
        """Register a Windows console event handler to catch the 'X' button or Ctrl+C."""
        def console_handler(event_type):
            if event_type == 2:  # CTRL_CLOSE_EVENT (window closed)
                logging.info("X button clicked. Shutting down...")
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(self.shutdown)
            return False  # Let other handlers process if needed
=======
        def console_handler(event_type):
            if event_type == 2:
                logging.info("X button clicked. Shutting down...")
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(self.shutdown)
            return False
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487

        ConsoleEventDelegate = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int)
        self._handler_ref = ConsoleEventDelegate(console_handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(self._handler_ref, True)

    def shutdown(self):
<<<<<<< HEAD
        """Initiate graceful shutdown by setting the exit event and closing server."""
=======
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
        if not self.exit_event.is_set():
            self.exit_event.set()
            if self.checker_task:
                self.checker_task.cancel()
            if self.server:
                self.server.close()

    async def cleanup(self):
<<<<<<< HEAD
        """Close all client connections and shut down the server cleanly."""
=======
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
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
<<<<<<< HEAD
    """Entry point for the asyncio server."""
=======
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
    server_instance = Server()
    try:
        await server_instance.start()
    finally:
        await server_instance.cleanup()

<<<<<<< HEAD

if __name__ == '__main__':
    # Create the global CNCSessionManager instance
    session_manager = CNCSessionManager()

    # Run the Flask dashboard in a separate thread (daemon)
=======
if __name__ == '__main__':
    session_manager = CNCSessionManager()

    # اجرای Flask در یک Thread کاملاً مجزا
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
    flask_thread = threading.Thread(
        target=run_flask_dashboard, 
        args=(session_manager,), 
        daemon=True
    )
    flask_thread.start()
<<<<<<< HEAD
    logging.info("Flask dashboard thread started")

    # Run the main asyncio TCP server
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Server stopped via KeyboardInterrupt.")
=======

    # اجرای سرور اصلی asyncio (TCP)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped via KeyboardInterrupt.")
>>>>>>> 17a1a9fb336644db92ca4bef6f277c5d46162487
