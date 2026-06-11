
import threading
import logging
import io
import pandas as pd
from flask import Flask, render_template, jsonify, request, send_file

app = Flask(__name__)
session_manager = None
logging.getLogger("werkzeug").setLevel(logging.ERROR)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/boards')
def get_boards():
    if session_manager is None:
        return jsonify({"error": "Manager not initialized"})
    data = session_manager.get_all_boards_status()
    return jsonify(data)


# مسیر جدید برای نمایش صفحه انتخاب تاریخ
@app.route('/export-page')
def export_page():
    return render_template('export.html')

# مسیر جدید برای تولید و دانلود فایل اکسل
@app.route('/api/export-excel', methods=['GET'])
def export_excel():
    if session_manager is None:
        return "Manager not initialized", 500

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        return "لطفا هر دو تاریخ را انتخاب کنید.", 400


    try:
        raw_data = session_manager.get_data_between_dates(start_date, end_date)
    except AttributeError:
        # اگر متد را هنوز نساخته‌اید، یک دیتای تستی می‌سازیم تا ارور ندهد
        raw_data = [
            {"id": 1, "date": start_date, "status": "test 1"},
            {"id": 2, "date": end_date, "status": "test 2"}
        ]

    # تبدیل داده ها به DataFrame پانداس
    df = pd.DataFrame(raw_data)

    # اگر داده ای وجود نداشت
    if df.empty:
        return "داده ای در این بازه زمانی یافت نشد.", 404

    # ساخت فایل اکسل در حافظه (بدون ذخیره روی هارد)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Export')
    output.seek(0)

    # ارسال فایل به کاربر برای دانلود
    return send_file(
        output,
        download_name=f"export_{start_date}_to_{end_date}.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def run_flask_dashboard(manager_instance):
    global session_manager
    session_manager = manager_instance
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
