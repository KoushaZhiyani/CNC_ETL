import asyncio

async def tcp_client():
    host = '192.168.1.147' # آی‌پی دستگاهی که باید به آن وصل شوید (سرور)
    port = 100             # پورتی که دستگاه روی آن گوش می‌دهد

    print(f"Connecting to {host}:{port}...")
    try:
        # ایجاد اتصال به سرور
        reader, writer = await asyncio.open_connection(host, port)
        print("Connected!")

        # ارسال یک پیام/درخواست به سرور (بایت)
        # اگر دستگاه شما نیاز به کامند خاصی دارد، آن را اینجا جایگزین کنید
        message = b'\x00' # به عنوان مثال
        print(f"Sending: {message}")
        writer.write(message)
        await writer.drain()

        # منتظر ماندن برای دریافت پاسخ
        data = await reader.read(256)
        print(f"Received from server: {data}")

        # بستن اتصال
        print("Closing connection...")
        writer.close()
        await writer.wait_closed()

    except Exception as e:
        print(f"Error: {e}")


asyncio.run(tcp_client())
