from flask import Flask, request, Response, render_template, redirect, url_for, session, flash, jsonify
from collections import OrderedDict
import json
import datetime
from dateutil.relativedelta import relativedelta
from db import get_connection
from passlib.hash import pbkdf2_sha256
from functools import wraps
import sys
import os
import socket

def get_server_info():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))  # 외부로 연결 시도 (실제 전송 없음)
        ip = s.getsockname()[0]
        s.close()
    except:
        ip = '127.0.0.1'

    port = 5000  # 현재 하단 run_server에서 고정값이므로 하드코딩
    return ip, port


def is_port_in_use(port=5000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

if is_port_in_use():
    print("이미 실행 중입니다.")
    sys.exit()


if getattr(sys, 'frozen', False):  # PyInstaller로 빌드된 경우
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
app.secret_key = 'your-secret-key-here'  # 실제 운영 환경에서는 안전한 키로 변경 필요

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    server_ip, server_port = get_server_info()
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('calendar.html', server_ip=server_ip, server_port=server_port)

@app.route('/calendar')
@login_required
def calendar():
    server_ip, server_port = get_server_info()
    return render_template('calendar.html', server_ip=server_ip, server_port=server_port)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    server_ip, server_port = get_server_info()

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user and pbkdf2_sha256.verify(password, user['password_hash']):
            session['user_id'] = user['id']
            session['username'] = user['username']
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        
        flash('아이디 또는 비밀번호가 잘못되었습니다.')
    return render_template('login.html', server_ip=server_ip, server_port=server_port)

@app.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        new_username = request.form.get('new_username')
        
        if not current_password:
            flash('현재 비밀번호를 입력해주세요.', 'danger')
            return redirect(url_for('change_password'))
        
        if new_password and new_password != confirm_password:
            flash('새 비밀번호가 일치하지 않습니다.', 'danger')
            return redirect(url_for('change_password'))
        
        if not new_password and not new_username:
            flash('아이디 또는 비밀번호 중 하나는 변경해야 합니다.', 'danger')
            return redirect(url_for('change_password'))
        
        conn = get_connection()
        cur = conn.cursor()
        
        # 현재 비밀번호 확인
        cur.execute('SELECT password_hash FROM users WHERE id = ?', (session['user_id'],))
        user = cur.fetchone()
        
        if not user or not pbkdf2_sha256.verify(current_password, user['password_hash']):
            flash('현재 비밀번호가 잘못되었습니다.', 'danger')
            cur.close()
            conn.close()
            return redirect(url_for('change_password'))
        
        try:
            if new_username:
                # 아이디 중복 확인
                cur.execute('SELECT id FROM users WHERE username = ? AND id != ?', 
                           (new_username, session['user_id']))
                if cur.fetchone():
                    flash('이미 사용 중인 아이디입니다.', 'danger')
                    return redirect(url_for('change_password'))
                
                # 아이디 변경
                cur.execute('UPDATE users SET username = ? WHERE id = ?',
                            (new_username, session['user_id']))
                session['username'] = new_username
                flash('아이디가 변경되었습니다.', 'success')
            
            if new_password:
                # 비밀번호 변경
                new_password_hash = pbkdf2_sha256.hash(new_password)
                cur.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                            (new_password_hash, session['user_id']))
                flash('비밀번호가 변경되었습니다.', 'success')
            
            conn.commit()
            return redirect(url_for('index'))
            
        except Exception as e:
            conn.rollback()
            flash('오류가 발생했습니다. 다시 시도해주세요.', 'danger')
            return redirect(url_for('change_password'))
        
        finally:
            cur.close()
            conn.close()
    
    return render_template('change_password.html')

@app.route('/credits')
def credits():
    return """
    <div style='text-align:center; margin-top:50px; font-family:sans-serif; color:#555;'>
        <h3>PharmaDay</h3>
        <p>Made by <strong>Cephalosporin</strong></p>
        <p>© 2025. All rights reserved.</p>
        <a href="/" style="color:#888;">← 돌아가기</a>
    </div>
    """


@app.route('/')
@login_required
def home():
    return "PharmaDay 백엔드 작동 중!"

@app.route('/report', methods=['POST'])
@login_required
def create_report():
    data = request.get_json()
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO daily_reports (date, total_sales, prescription_count, notes, is_holiday, is_manual_holiday)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data['date'],
            data['total_sales'],
            data.get('prescription_count', 0),
            data.get('notes', ''),
            data.get('is_holiday', False),
            data.get('is_manual_holiday', False)
        ))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "정산 등록 완료!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/report', methods=['GET'])
@login_required
def get_reports():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM daily_reports ORDER BY date DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        reports = []
        for row in rows:
            reports.append(OrderedDict([
                ("id", row['id']),
                ("date", str(row['date'])),
                ("total_sales", row['total_sales']),
                ("prescription_count", row['prescription_count']),
                ("notes", row['notes']),
                ("is_holiday", bool(row['is_holiday'])),
                ("is_manual_holiday", bool(row['is_manual_holiday'])),
            ]))

        return Response(
            json.dumps(reports, ensure_ascii=False),
            mimetype='application/json'
        )

    except Exception as e:
        return Response(json.dumps({"error": str(e)}), status=500, mimetype='application/json')    

@app.route('/calendar-data', methods=['GET'])
@login_required
def get_calendar_data():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT date, total_sales, prescription_count, notes, is_holiday, is_manual_holiday FROM daily_reports")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        data = []
        for row in rows:
            date_str = row['date']
            if isinstance(date_str, datetime.date):
                date_obj = date_str
            else:
                date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            
            weekday_num = date_obj.weekday()
            weekday_str = ["월", "화", "수", "목", "금", "토", "일"][weekday_num]
            
            # SQLite에서는 boolean이 0 또는 1로 저장되므로 명시적 변환 필요
            is_holiday = bool(row['is_holiday'])
            is_manual_holiday = bool(row['is_manual_holiday'])
            
            if is_holiday:
                holiday_type = "holiday"
            elif is_manual_holiday:
                holiday_type = "manual"
            else:
                holiday_type = "none"

            # 매출과 처방건수가 None이면 0으로 처리
            total_sales = row['total_sales'] if row['total_sales'] is not None else 0
            prescription_count = row['prescription_count'] if row['prescription_count'] is not None else 0
            
            data.append(OrderedDict([
                ("start", str(date_obj)),
                ("title", f"₩{total_sales:,} / 처방 {prescription_count}건"),
                ("notes", row['notes'] or ''),
                ("is_holiday", is_holiday),
                ("is_manual_holiday", is_manual_holiday),
                ("holiday_type", holiday_type),
                ("weekday", weekday_str),
                ("is_saturday", weekday_num == 5),
                ("is_sunday", weekday_num == 6),
                ("allDay", True),
                ("backgroundColor", "#ffebee" if is_holiday or is_manual_holiday else None)
            ]))

        return Response(json.dumps(data, ensure_ascii=False), mimetype='application/json')

    except Exception as e:
        return Response(json.dumps({"error": str(e)}), status=500, mimetype='application/json')

@app.route('/report/<date_str>', methods=['GET'])
@login_required
def get_report_by_date(date_str):
    try:
        try:
            date_obj = date_str if isinstance(date_str, datetime.date) else datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(json.dumps({"error": "날짜 형식이 잘못되었습니다. YYYY-MM-DD 형식이어야 합니다."}, ensure_ascii=False),
                            status=400, mimetype='application/json')

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT date, total_sales, prescription_count, notes, is_holiday, is_manual_holiday
            FROM daily_reports
            WHERE date = ?
        """, (date_obj,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row is None:
            return Response(json.dumps({"error": "해당 날짜의 정산 정보가 없습니다."}, ensure_ascii=False),
                            status=404, mimetype='application/json')

        result = OrderedDict([
            ("date", str(row['date'])),
            ("total_sales", row['total_sales']),
            ("prescription_count", row['prescription_count']),
            ("notes", row['notes']),
            ("is_holiday", bool(row['is_holiday'])),
            ("is_manual_holiday", bool(row['is_manual_holiday']))
        ])

        return Response(json.dumps(result, ensure_ascii=False), mimetype='application/json')

    except Exception as e:
        return Response(json.dumps({"error": str(e)}), status=500, mimetype='application/json')

@app.route('/report/<date_str>', methods=['PUT'])
@login_required
def upsert_report_by_date(date_str):
    try:
        try:
            date_obj = date_str if isinstance(date_str, datetime.date) else datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(json.dumps({"error": "날짜 형식이 잘못되었습니다. YYYY-MM-DD 형식이어야 합니다."}, ensure_ascii=False),
                            status=400, mimetype='application/json')

        data = request.get_json()
        
        # date_str parsed earlier; parse again to ensure a date object
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()

        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO daily_reports (
                  date, total_sales, prescription_count, notes, is_holiday, is_manual_holiday
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                  total_sales = excluded.total_sales,
                  prescription_count = excluded.prescription_count,
                  notes = excluded.notes,
                  is_holiday = excluded.is_holiday,
                  is_manual_holiday = excluded.is_manual_holiday
            """, (
                date_obj,
                int(data['total_sales']),
                int(data.get('prescription_count', 0)),
                data.get('notes', ''),
                bool(data.get('is_holiday', False)),
                bool(data.get('is_manual_holiday', False))
            ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

        return Response(json.dumps({"message": "정산 정보가 저장되었습니다 (등록 또는 수정됨)."}, ensure_ascii=False),
                        status=200, mimetype='application/json')

    except Exception as e:
        return Response(json.dumps({"error": str(e)}), status=500, mimetype='application/json')



@app.route('/report/monthly')
@login_required
def get_monthly_reports():
    year = request.args.get('year')
    month = request.args.get('month')

    if not year or not month:
        return jsonify({"error": "year and month are required"}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT date, total_sales, prescription_count, notes, is_holiday, is_manual_holiday
            FROM daily_reports
            WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
        """, (year, month))

        rows = cur.fetchall()
        result = {
            row['date']: {
                'total_sales': row['total_sales'],
                'prescription_count': row['prescription_count'],
                'notes': row['notes'],
                'is_holiday': row['is_holiday'],
                'is_manual_holiday': row['is_manual_holiday']
            }
            for row in rows
        }

        cur.close()
        conn.close()

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/report/<date_str>', methods=['DELETE'])
@login_required
def delete_report_by_date(date_str):
    try:
        try:
            date_obj = date_str if isinstance(date_str, datetime.date) else datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "날짜 형식이 잘못되었습니다. YYYY-MM-DD 형식이어야 합니다."}), 400

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM daily_reports WHERE date = ?", (date_str,))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": f"{date_str}의 정산 정보가 삭제되었습니다."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/analyze', methods=['GET'])
@login_required
def analyze_data():
    return render_template("analyze.html")

@app.route('/report/analyze')
@login_required
def analyze_report():
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    include_saturday = request.args.get('include_saturday', 'true') == 'true'
    unit = request.args.get('unit', 'day')

    if not start_date or not end_date:
        return jsonify({'error': 'start and end required'}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()

        if unit == 'month':
            # 월별 집계 시 토요일 포함 여부 처리
            include_saturday_sql = '' if include_saturday else "AND strftime('%w', date) != '6'"
            
            cur.execute(f"""
                SELECT strftime('%Y-%m', date) as month,
                       SUM(total_sales) as sales,
                       SUM(prescription_count) as prescriptions
                FROM daily_reports
                WHERE date >= ? AND date <= ?
                  AND NOT is_holiday AND NOT is_manual_holiday
                  AND strftime('%w', date) != '0'
                  {include_saturday_sql}
                GROUP BY strftime('%Y-%m', date)
                ORDER BY month
            """, (start_date, end_date))

            rows = cur.fetchall()

            total_sales = 0
            total_prescriptions = 0
            trend = []
            max_pres = -1
            min_pres = float('inf')
            max_pres_date = ''
            min_pres_date = ''
            max_sales = -1
            min_sales = float('inf')
            max_month = ""
            min_month = ""

            for row in rows:
                month = row['month']
                sales = int(row['sales'] or 0)
                prescriptions = int(row['prescriptions'] or 0)

                trend.append({'date': month, 'sales': sales, 'prescriptions': prescriptions})
                total_sales += sales
                total_prescriptions += prescriptions

                if sales > max_sales:
                    max_sales = sales
                    max_month = month
                if sales < min_sales:
                    min_sales = sales
                    min_month = month

                if prescriptions > max_pres:
                    max_pres = prescriptions
                    max_pres_date = month
                if prescriptions < min_pres:
                    min_pres = prescriptions
                    min_pres_date = month

            avg_sales = round(total_sales / len(trend), 2) if trend else 0

            return jsonify({
                'summary': {
                    'total_sales': total_sales,
                    'total_prescriptions': total_prescriptions,
                    'average_sales': avg_sales,
                    'average_prescriptions': round(total_prescriptions / len(trend), 2) if trend else 0,
                    'max_sales_date': max_month,
                    'min_sales_date': min_month,
                    'max_prescriptions_date': max_pres_date,
                    'min_prescriptions_date': min_pres_date
                },
                'trend': trend
            })

        else:
            cur.execute("""
                SELECT date, total_sales, prescription_count, is_holiday, is_manual_holiday
                FROM daily_reports
                WHERE date BETWEEN ? AND ?
            """, (start_date, end_date))

            rows = cur.fetchall()

            total_sales = 0
            total_prescriptions = 0
            trend = []
            max_pres = -1
            min_pres = float('inf')
            max_pres_date = ''
            min_pres_date = ''
            max_sales = -1
            min_sales = float('inf')
            max_date = ""
            min_date = ""

            for row in rows:
                date_str = row['date']
                if isinstance(date_str, datetime.date):
                    date_obj = date_str
                else:
                    date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                
                weekday = date_obj.weekday()
                is_holiday = bool(row['is_holiday'])
                is_manual_holiday = bool(row['is_manual_holiday'])

                if weekday == 6 or is_holiday or is_manual_holiday:
                    continue
                if not include_saturday and weekday == 5:
                    continue

                sales = int(row['total_sales'] or 0)
                count = int(row['prescription_count'] or 0)
                date_str = date_obj.strftime('%Y-%m-%d')
                trend.append({'date': date_str, 'sales': sales, 'prescriptions': count})

                total_sales += sales
                total_prescriptions += count

                if sales > max_sales:
                    max_sales = sales
                    max_date = date_str
                if sales < min_sales:
                    min_sales = sales
                    min_date = date_str

                if count > max_pres:
                    max_pres = count
                    max_pres_date = date_str
                if count < min_pres:
                    min_pres = count
                    min_pres_date = date_str

            trend.sort(key=lambda x: x['date'])
            avg_sales = round(total_sales / len(trend), 2) if trend else 0

            return jsonify({
                'summary': {
                    'total_sales': total_sales,
                    'total_prescriptions': total_prescriptions,
                    'average_sales': avg_sales,
                    'average_prescriptions': round(total_prescriptions / len(trend), 2) if trend else 0,
                    'max_sales_date': max_date,
                    'min_sales_date': min_date,
                    'max_prescriptions_date': max_pres_date,
                    'min_prescriptions_date': min_pres_date
                },
                'trend': trend
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import webbrowser
    import threading
    import time

    # 서버 실행 (새 스레드)
    def run_server():
        app.run(host='0.0.0.0', port=5000, debug=False)

    threading.Thread(target=run_server).start()

    # 서버가 뜨길 잠깐 기다렸다가 브라우저 자동 실행
    time.sleep(3)
    webbrowser.open("http://127.0.0.1:5000")



