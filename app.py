from flask import Flask, request, redirect, url_for, render_template_string, g
import sqlite3

app = Flask(__name__)
app.config['DATABASE'] = 'db.sqlite'

# --- 1. РОБОТА З БАЗОЮ ДАНИХ ---
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, message TEXT);
        CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT, email TEXT, phone TEXT);
        CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, price REAL);
        CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, status TEXT DEFAULT 'Нове', FOREIGN KEY(client_id) REFERENCES clients(id));
        CREATE TABLE IF NOT EXISTS order_items (order_id INTEGER, product_id INTEGER, quantity INTEGER, FOREIGN KEY(order_id) REFERENCES orders(id));
    ''')
    
    db.execute("INSERT OR IGNORE INTO clients (id, full_name, email, phone) VALUES (1, 'Іван Франко', 'ivan@mail.com', '+380991234567')")
    db.execute("INSERT OR IGNORE INTO clients (id, full_name, email, phone) VALUES (2, 'Леся Українка', 'lesya@mail.com', '+380997654321')")
    
    db.execute("INSERT OR IGNORE INTO products (id, title, price) VALUES (1, 'Ноутбук Lenovo', 25000)")
    db.execute("INSERT OR IGNORE INTO products (id, title, price) VALUES (2, 'Мишка Logitech', 1200)")
    db.execute("INSERT OR IGNORE INTO products (id, title, price) VALUES (3, 'Клавіатура', 2500)")
    
    db.execute("INSERT OR IGNORE INTO orders (id, client_id, status) VALUES (1, 1, 'Нове')")
    db.commit()

# --- 2. ШАБЛОН ДИЗАЙНУ (HTML + CSS) ---
# ЗМІНЕНО: %s на {{content}}
LAYOUT = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <title>Лабораторна 4</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f7f6; margin: 0; padding: 0; }
        .navbar { background-color: #2c3e50; overflow: hidden; padding: 15px; }
        .navbar a { color: white; text-decoration: none; margin-right: 20px; font-weight: bold; }
        .navbar a:hover { color: #3498db; }
        .container { max-width: 800px; margin: 20px auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        h2 { color: #2c3e50; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background-color: #3498db; color: white; }
        input, textarea, select { width: 100%; padding: 8px; margin: 5px 0 15px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        button { background-color: #3498db; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background-color: #2980b9; }
        .btn-delete { background-color: #e74c3c; color: white; padding: 5px 10px; text-decoration: none; border-radius: 4px; }
        .btn-delete:hover { background-color: #c0392b; }
    </style>
</head>
<body>
    <div class="navbar">
        <a href="/">📝 Відгуки</a>
        <a href="/shop">🛒 Магазин</a>
        <a href="/admin">📦 Замовлення</a>
        <a href="/admin/clients">👥 Клієнти</a>
    </div>
    <div class="container">
        {{content}}
    </div>
</body>
</html>
"""

# --- 3. МАРШРУТИ (Сторінки сайту) ---

@app.route('/', methods=['GET', 'POST'])
def index():
    db = get_db()
    if request.method == 'POST':
        db.execute('INSERT INTO feedback (name, message) VALUES (?, ?)', (request.form['name'], request.form['message']))
        db.commit()
        return redirect('/')
    
    feedbacks = db.execute('SELECT * FROM feedback ORDER BY id DESC').fetchall()
    
    html = "<h2>Залишити відгук</h2>"
    html += "<form method='POST'>"
    html += "Ім'я: <input type='text' name='name' required>"
    html += "Повідомлення: <textarea name='message' required></textarea>"
    html += "<button type='submit'>Відправити</button></form><hr>"
    
    html += "<h2>Всі відгуки</h2>"
    for f in feedbacks:
        html += f"<p><b>{f['name']}</b>: {f['message']} <a class='btn-delete' href='/delete_feedback/{f['id']}'>Видалити</a></p>"
    
    return render_template_string(LAYOUT.replace('{{content}}', html))

@app.route('/delete_feedback/<int:id>')
def delete_feedback(id):
    db = get_db()
    db.execute('DELETE FROM feedback WHERE id=?', (id,))
    db.commit()
    return redirect('/')

@app.route('/shop')
def shop():
    db = get_db()
    products = db.execute('SELECT * FROM products').fetchall()
    
    html = "<h2>Список товарів</h2><table><tr><th>ID</th><th>Назва</th><th>Ціна (грн)</th></tr>"
    for p in products:
        html += f"<tr><td>{p['id']}</td><td>{p['title']}</td><td>{p['price']}</td></tr>"
    html += "</table>"
    
    return render_template_string(LAYOUT.replace('{{content}}', html))

@app.route('/admin')
def admin():
    db = get_db()
    orders = db.execute('SELECT orders.id, orders.status, clients.full_name FROM orders LEFT JOIN clients ON orders.client_id = clients.id').fetchall()
    
    html = "<h2>Керування замовленнями</h2><table><tr><th>ID</th><th>Клієнт</th><th>Статус</th><th>Дія</th></tr>"
    for o in orders:
        html += f"<tr><td>{o['id']}</td><td>{o['full_name'] or 'Немає'}</td><td>{o['status']}</td>"
        html += f"""<td>
            <form method='POST' action='/admin/status/{o['id']}' style='margin:0;'>
                <select name='status' style='width: 120px; display:inline;'>
                    <option>Нове</option><option>В обробці</option><option>Виконано</option>
                </select>
                <button type='submit' style='padding: 5px;'>ОК</button>
            </form>
        </td></tr>"""
    html += "</table>"
    
    return render_template_string(LAYOUT.replace('{{content}}', html))

@app.route('/admin/status/<int:id>', methods=['POST'])
def update_status(id):
    db = get_db()
    db.execute('UPDATE orders SET status=? WHERE id=?', (request.form['status'], id))
    db.commit()
    return redirect('/admin')

@app.route('/admin/clients', methods=['GET', 'POST'])
def clients():
    db = get_db()
    if request.method == 'POST':
        db.execute('INSERT INTO clients (full_name, email, phone) VALUES (?, ?, ?)', (request.form['full_name'], request.form['email'], request.form['phone']))
        db.commit()
        return redirect('/admin/clients')
    
    all_clients = db.execute('SELECT * FROM clients').fetchall()
    
    html = "<h2>База клієнтів (Рівень 2)</h2>"
    html += "<h3>Додати нового клієнта</h3>"
    html += "<form method='POST'>"
    html += "ПІБ: <input type='text' name='full_name' required>"
    html += "Email: <input type='email' name='email'>"
    html += "Телефон: <input type='text' name='phone'>"
    html += "<button type='submit'>Додати</button></form>"
    
    html += "<table><tr><th>ID</th><th>ПІБ</th><th>Email</th><th>Телефон</th><th>Дія</th></tr>"
    for c in all_clients:
        html += f"<tr><td>{c['id']}</td><td>{c['full_name']}</td><td>{c['email']}</td><td>{c['phone']}</td>"
        html += f"<td><a class='btn-delete' href='/admin/clients/delete/{c['id']}'>Видалити</a></td></tr>"
    html += "</table>"
    
    return render_template_string(LAYOUT.replace('{{content}}', html))

@app.route('/admin/clients/delete/<int:id>')
def delete_client(id):
    db = get_db()
    db.execute('DELETE FROM clients WHERE id=?', (id,))
    db.commit()
    return redirect('/admin/clients')

# --- 4. ЗАПУСК ---
if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)
