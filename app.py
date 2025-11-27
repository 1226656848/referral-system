"""
鑫洁口腔 - 患者转介绍管理系统 (云端版)
"""

from flask import Flask, render_template_string, request, redirect, url_for
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'xinjie_dental_2024'

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            type TEXT DEFAULT '老患者',
            referrals INTEGER DEFAULT 0,
            converted INTEGER DEFAULT 0,
            rewards REAL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            referrer_id INTEGER,
            treatment TEXT,
            amount REAL DEFAULT 0,
            is_converted INTEGER DEFAULT 0,
            referral_date TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            type TEXT DEFAULT '现金',
            amount REAL DEFAULT 0,
            date TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def update_referrer_stats(referrer_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM patients WHERE referrer_id = ?', (referrer_id,))
    referrals = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM patients WHERE referrer_id = ? AND is_converted = 1', (referrer_id,))
    converted = cursor.fetchone()[0]
    cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM rewards WHERE referrer_id = ?', (referrer_id,))
    rewards = cursor.fetchone()[0]
    cursor.execute('UPDATE referrers SET referrals=?, converted=?, rewards=? WHERE id=?', 
                   (referrals, converted, rewards, referrer_id))
    conn.commit()
    conn.close()

# HTML模板
BASE_HTML = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <title>转介绍管理</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #F1F5F9; color: #1E293B; padding-bottom: 70px; }
        .header { background: linear-gradient(135deg, #3B82F6, #2563EB); color: white; padding: 15px 20px; position: sticky; top: 0; z-index: 100; }
        .header h1 { font-size: 18px; }
        .content { padding: 15px; }
        .card { background: white; border-radius: 12px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
        .card-title { font-size: 16px; font-weight: 600; margin-bottom: 15px; }
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
        .stat-item { text-align: center; padding: 12px 5px; background: #F8FAFC; border-radius: 10px; }
        .stat-icon { font-size: 24px; margin-bottom: 5px; }
        .stat-value { font-size: 18px; font-weight: 700; color: #3B82F6; }
        .stat-label { font-size: 11px; color: #64748B; }
        .btn { display: block; width: 100%; padding: 12px; border-radius: 10px; font-size: 15px; font-weight: 600; text-decoration: none; text-align: center; border: none; cursor: pointer; margin-bottom: 10px; }
        .btn-primary { background: linear-gradient(135deg, #3B82F6, #2563EB); color: white; }
        .btn-success { background: linear-gradient(135deg, #10B981, #059669); color: white; }
        .btn-warning { background: linear-gradient(135deg, #F59E0B, #D97706); color: white; }
        .btn-danger { background: #EF4444; color: white; }
        .btn-sm { display: inline-block; width: auto; padding: 6px 12px; font-size: 12px; margin: 2px; }
        .form-group { margin-bottom: 15px; }
        .form-label { display: block; font-size: 14px; margin-bottom: 6px; }
        .form-input, .form-select { width: 100%; padding: 12px; border: 1px solid #D1D5DB; border-radius: 10px; font-size: 16px; }
        .list-item { display: flex; align-items: center; padding: 12px 0; border-bottom: 1px solid #E2E8F0; }
        .list-avatar { width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, #3B82F6, #8B5CF6); display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; margin-right: 12px; font-size: 14px; }
        .list-info { flex: 1; }
        .list-name { font-weight: 600; }
        .list-detail { font-size: 12px; color: #64748B; }
        .badge { padding: 3px 8px; border-radius: 10px; font-size: 11px; }
        .badge-success { background: #D1FAE5; color: #059669; }
        .badge-warning { background: #FEF3C7; color: #D97706; }
        .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; background: white; display: flex; justify-content: space-around; padding: 8px 0; box-shadow: 0 -2px 10px rgba(0,0,0,0.1); }
        .nav-item { display: flex; flex-direction: column; align-items: center; color: #64748B; font-size: 11px; text-decoration: none; padding: 5px 15px; }
        .nav-item.active { color: #3B82F6; }
        .nav-item span { font-size: 20px; }
        .empty { text-align: center; padding: 30px; color: #94A3B8; }
    </style>
</head>
<body>
    <header class="header"><h1>{{ title }}</h1></header>
    <div class="content">{{ content | safe }}</div>
    <nav class="bottom-nav">
        <a href="/" class="nav-item {{ 'active' if page == 'home' else '' }}"><span>🏠</span>首页</a>
        <a href="/referrers" class="nav-item {{ 'active' if page == 'referrers' else '' }}"><span>👥</span>介绍人</a>
        <a href="/patients" class="nav-item {{ 'active' if page == 'patients' else '' }}"><span>🧑‍⚕️</span>患者</a>
        <a href="/rewards" class="nav-item {{ 'active' if page == 'rewards' else '' }}"><span>🎁</span>奖励</a>
    </nav>
</body>
</html>
'''

@app.route('/')
def index():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referrers")
    ref_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM patients")
    pat_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM patients WHERE is_converted = 1")
    converted = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(amount), 0) FROM patients")
    revenue = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(amount), 0) FROM rewards")
    rewards = c.fetchone()[0]
    rate = (converted / pat_count * 100) if pat_count > 0 else 0
    
    c.execute("SELECT * FROM referrers ORDER BY converted DESC LIMIT 5")
    top = c.fetchall()
    conn.close()
    
    rank_html = ""
    for i, r in enumerate(top):
        rank_html += f'<div class="list-item"><div class="list-avatar">{i+1}</div><div class="list-info"><div class="list-name">{r["name"]}</div><div class="list-detail">介绍{r["referrals"]}人·成交{r["converted"]}人</div></div><span style="color:#F59E0B;font-weight:600">¥{r["rewards"]:.0f}</span></div>'
    if not top:
        rank_html = '<div class="empty">暂无数据</div>'
    
    content = f'''
    <div class="card">
        <div class="stats-grid">
            <div class="stat-item"><div class="stat-icon">👥</div><div class="stat-value">{ref_count}</div><div class="stat-label">介绍人</div></div>
            <div class="stat-item"><div class="stat-icon">🧑‍⚕️</div><div class="stat-value">{pat_count}</div><div class="stat-label">总患者</div></div>
            <div class="stat-item"><div class="stat-icon">✅</div><div class="stat-value">{converted}</div><div class="stat-label">已成交</div></div>
            <div class="stat-item"><div class="stat-icon">💰</div><div class="stat-value">{revenue:.0f}</div><div class="stat-label">总营收</div></div>
            <div class="stat-item"><div class="stat-icon">🎁</div><div class="stat-value">{rewards:.0f}</div><div class="stat-label">已发奖励</div></div>
            <div class="stat-item"><div class="stat-icon">📊</div><div class="stat-value">{rate:.0f}%</div><div class="stat-label">转化率</div></div>
        </div>
    </div>
    <div class="card">
        <div class="card-title">⚡ 快捷操作</div>
        <a href="/referrer/add" class="btn btn-primary">➕ 新增介绍人</a>
        <a href="/patient/add" class="btn btn-success">➕ 新增患者</a>
    </div>
    <div class="card">
        <div class="card-title">🏆 介绍人排行</div>
        {rank_html}
    </div>
    '''
    return render_template_string(BASE_HTML, title="🦷 转介绍管理系统", content=content, page="home")

@app.route('/referrers')
def referrers():
    conn = get_db()
    refs = conn.execute("SELECT * FROM referrers ORDER BY converted DESC").fetchall()
    conn.close()
    
    html = '<a href="/referrer/add" class="btn btn-success">➕ 新增介绍人</a><div class="card">'
    if refs:
        for r in refs:
            html += f'''<div class="list-item">
                <div class="list-avatar">{r["name"][0]}</div>
                <div class="list-info">
                    <div class="list-name">{r["name"]}</div>
                    <div class="list-detail">📱{r["phone"] or "-"} · {r["type"]}</div>
                    <div class="list-detail">介绍{r["referrals"]}人·成交{r["converted"]}人·奖励¥{r["rewards"]:.0f}</div>
                    <div><a href="/referrer/del/{r["id"]}" class="btn btn-danger btn-sm" onclick="return confirm('确定删除?')">删除</a></div>
                </div>
            </div>'''
    else:
        html += '<div class="empty">暂无介绍人</div>'
    html += '</div>'
    return render_template_string(BASE_HTML, title="👥 介绍人管理", content=html, page="referrers")

@app.route('/referrer/add', methods=['GET', 'POST'])
def add_referrer():
    if request.method == 'POST':
        conn = get_db()
        conn.execute("INSERT INTO referrers (name, phone, type) VALUES (?, ?, ?)",
                    (request.form['name'], request.form.get('phone', ''), request.form.get('type', '老患者')))
        conn.commit()
        conn.close()
        return redirect('/referrers')
    
    html = '''<div class="card">
        <div class="card-title">👥 新增介绍人</div>
        <form method="POST">
            <div class="form-group"><label class="form-label">姓名 *</label><input name="name" class="form-input" required></div>
            <div class="form-group"><label class="form-label">电话</label><input name="phone" class="form-input"></div>
            <div class="form-group"><label class="form-label">类型</label>
                <select name="type" class="form-select">
                    <option>老患者</option><option>员工推荐</option><option>合作商家</option>
                </select>
            </div>
            <button type="submit" class="btn btn-success">💾 保存</button>
            <a href="/referrers" class="btn" style="background:#94A3B8;color:white">取消</a>
        </form>
    </div>'''
    return render_template_string(BASE_HTML, title="新增介绍人", content=html, page="referrers")

@app.route('/referrer/del/<int:id>')
def del_referrer(id):
    conn = get_db()
    conn.execute("DELETE FROM referrers WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect('/referrers')

@app.route('/patients')
def patients():
    conn = get_db()
    pats = conn.execute("""SELECT p.*, r.name as ref_name FROM patients p 
                          LEFT JOIN referrers r ON p.referrer_id = r.id 
                          ORDER BY p.created_at DESC""").fetchall()
    conn.close()
    
    html = '<a href="/patient/add" class="btn btn-success">➕ 新增患者</a><div class="card">'
    if pats:
        for p in pats:
            status = "已成交" if p["is_converted"] else "待跟进"
            badge = "badge-success" if p["is_converted"] else "badge-warning"
            html += f'''<div class="list-item">
                <div class="list-avatar" style="background:linear-gradient(135deg,#10B981,#059669)">{p["name"][0]}</div>
                <div class="list-info">
                    <div class="list-name">{p["name"]}</div>
                    <div class="list-detail">介绍人:{p["ref_name"] or "无"} · {p["treatment"] or "-"}</div>
                    <div class="list-detail">消费:¥{p["amount"]:.0f}</div>
                    <div><a href="/patient/del/{p["id"]}" class="btn btn-danger btn-sm" onclick="return confirm('确定删除?')">删除</a></div>
                </div>
                <span class="badge {badge}">{status}</span>
            </div>'''
    else:
        html += '<div class="empty">暂无患者</div>'
    html += '</div>'
    return render_template_string(BASE_HTML, title="🧑‍⚕️ 患者管理", content=html, page="patients")

@app.route('/patient/add', methods=['GET', 'POST'])
def add_patient():
    conn = get_db()
    if request.method == 'POST':
        ref_id = request.form.get('referrer_id') or None
        converted = 1 if request.form.get('is_converted') else 0
        conn.execute("""INSERT INTO patients (name, phone, referrer_id, treatment, amount, is_converted, referral_date) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (request.form['name'], request.form.get('phone', ''), ref_id,
                     request.form.get('treatment', ''), float(request.form.get('amount', 0) or 0),
                     converted, datetime.now().strftime('%Y-%m-%d')))
        conn.commit()
        if ref_id:
            update_referrer_stats(int(ref_id))
        conn.close()
        return redirect('/patients')
    
    refs = conn.execute("SELECT id, name FROM referrers ORDER BY name").fetchall()
    conn.close()
    
    options = '<option value="">请选择</option>' + ''.join([f'<option value="{r["id"]}">{r["name"]}</option>' for r in refs])
    html = f'''<div class="card">
        <div class="card-title">🧑‍⚕️ 新增患者</div>
        <form method="POST">
            <div class="form-group"><label class="form-label">姓名 *</label><input name="name" class="form-input" required></div>
            <div class="form-group"><label class="form-label">电话</label><input name="phone" class="form-input"></div>
            <div class="form-group"><label class="form-label">介绍人</label><select name="referrer_id" class="form-select">{options}</select></div>
            <div class="form-group"><label class="form-label">治疗项目</label><input name="treatment" class="form-input"></div>
            <div class="form-group"><label class="form-label">消费金额</label><input name="amount" type="number" class="form-input" value="0"></div>
            <div class="form-group"><label><input type="checkbox" name="is_converted" value="1"> 已成交</label></div>
            <button type="submit" class="btn btn-success">💾 保存</button>
            <a href="/patients" class="btn" style="background:#94A3B8;color:white">取消</a>
        </form>
    </div>'''
    return render_template_string(BASE_HTML, title="新增患者", content=html, page="patients")

@app.route('/patient/del/<int:id>')
def del_patient(id):
    conn = get_db()
    p = conn.execute("SELECT referrer_id FROM patients WHERE id = ?", (id,)).fetchone()
    ref_id = p["referrer_id"] if p else None
    conn.execute("DELETE FROM patients WHERE id = ?", (id,))
    conn.commit()
    if ref_id:
        update_referrer_stats(ref_id)
    conn.close()
    return redirect('/patients')

@app.route('/rewards')
def rewards():
    conn = get_db()
    rews = conn.execute("""SELECT rw.*, r.name as ref_name FROM rewards rw 
                          LEFT JOIN referrers r ON rw.referrer_id = r.id 
                          ORDER BY rw.created_at DESC""").fetchall()
    conn.close()
    
    html = '<a href="/reward/add" class="btn btn-warning">🎁 发放奖励</a><div class="card">'
    if rews:
        for r in rews:
            html += f'''<div class="list-item">
                <div class="list-avatar" style="background:linear-gradient(135deg,#F59E0B,#D97706)">🎁</div>
                <div class="list-info">
                    <div class="list-name">{r["ref_name"] or "未知"}</div>
                    <div class="list-detail">{r["type"]} · ¥{r["amount"]:.0f} · {r["date"] or "-"}</div>
                </div>
                <span class="badge badge-success">已发放</span>
            </div>'''
    else:
        html += '<div class="empty">暂无奖励记录</div>'
    html += '</div>'
    return render_template_string(BASE_HTML, title="🎁 奖励管理", content=html, page="rewards")

@app.route('/reward/add', methods=['GET', 'POST'])
def add_reward():
    conn = get_db()
    if request.method == 'POST':
        ref_id = int(request.form['referrer_id'])
        conn.execute("INSERT INTO rewards (referrer_id, type, amount, date) VALUES (?, ?, ?, ?)",
                    (ref_id, request.form.get('type', '现金'), 
                     float(request.form.get('amount', 0) or 0),
                     datetime.now().strftime('%Y-%m-%d')))
        conn.commit()
        update_referrer_stats(ref_id)
        conn.close()
        return redirect('/rewards')
    
    refs = conn.execute("SELECT id, name FROM referrers ORDER BY name").fetchall()
    conn.close()
    
    options = '<option value="">请选择</option>' + ''.join([f'<option value="{r["id"]}">{r["name"]}</option>' for r in refs])
    html = f'''<div class="card">
        <div class="card-title">🎁 发放奖励</div>
        <form method="POST">
            <div class="form-group"><label class="form-label">介绍人 *</label><select name="referrer_id" class="form-select" required>{options}</select></div>
            <div class="form-group"><label class="form-label">奖励类型</label>
                <select name="type" class="form-select"><option>现金</option><option>礼品</option><option>代金券</option></select>
            </div>
            <div class="form-group"><label class="form-label">金额</label><input name="amount" type="number" class="form-input" value="0"></div>
            <button type="submit" class="btn btn-warning">🎁 确认发放</button>
            <a href="/rewards" class="btn" style="background:#94A3B8;color:white">取消</a>
        </form>
    </div>'''
    return render_template_string(BASE_HTML, title="发放奖励", content=html, page="rewards")

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

