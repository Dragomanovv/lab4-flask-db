from flask import Flask, request, jsonify, render_template_string, g
from flasgger import Swagger
import sqlite3

app = Flask(__name__)
app.config['DATABASE'] = 'db.sqlite'

# Ініціалізація Swagger для документації (Рівень 2)
swagger = Swagger(app, template={
    "info": {
        "title": "API Магазину",
        "description": "Документація REST API для лаби 5",
        "version": "1.0.0"
    }
})

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
        CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, status TEXT DEFAULT 'Нове');
    ''')
    db.execute("INSERT OR IGNORE INTO clients (id, full_name, email, phone) VALUES (1, 'Іван Франко', 'ivan@mail.com', '+380991234567')")
    db.execute("INSERT OR IGNORE INTO products (id, title, price) VALUES (1, 'Ноутбук Lenovo', 25000)")
    db.execute("INSERT OR IGNORE INTO products (id, title, price) VALUES (2, 'Мишка Logitech', 1200)")
    db.commit()

# --- 2. БАЗОВИЙ САЙТ (З ЛАБИ 4) ---
LAYOUT = """
<!DOCTYPE html><html lang="uk"><head><meta charset="UTF-8"><title>Магазин</title>
<style>body{font-family:Arial;background:#f4f7f6;padding:20px;} .navbar a{margin-right:20px;} .container{background:white;padding:20px;border-radius:8px;}</style>
</head><body>
<div class="navbar"><a href="/">Відгуки</a> <a href="/shop">Магазин</a> <a href="/apidocs/">Документація API (Swagger)</a></div>
<div class="container">{{content}}</div></body></html>
"""

@app.route('/')
def index():
    return render_template_string(LAYOUT.replace('{{content}}', "<h2>Головна сторінка</h2><p>Перейдіть за посиланням вище, щоб подивитися документацію API.</p>"))

@app.route('/shop')
def shop():
    db = get_db()
    products = db.execute('SELECT * FROM products').fetchall()
    html = "<h2>Товари</h2>"
    for p in products:
        html += f"<p>{p['title']} - {p['price']} грн</p>"
    return render_template_string(LAYOUT.replace('{{content}}', html))


# ==========================================
# --- 3. REST API (РІВЕНЬ 1, 2 та 3) ---
# ==========================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Ресурс не знайдено (404)'}), 404

@app.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Некоректний запит (400). Перевірте JSON дані.'}), 400

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Внутрішня помилка сервера (500)'}), 500


@app.route('/api/v1/products', methods=['GET'])
def api_get_products():
    """
    Отримати список всіх товарів
    ---
    responses:
      200:
        description: Успішний список товарів
    """
    db = get_db()
    rows = db.execute('SELECT * FROM products').fetchall()
    return jsonify([dict(row) for row in rows]), 200


@app.route('/api/v1/products/<int:product_id>', methods=['GET'])
def api_get_product(product_id):
    """
    Отримати конкретний товар за ID
    ---
    parameters:
      - name: product_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Дані товару
      404:
        description: Товар не знайдено
    """
    row = get_db().execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if row is None:
        return jsonify({'error': 'Товар не знайдено'}), 404
    return jsonify(dict(row)), 200


@app.route('/api/v1/products', methods=['POST'])
def api_create_product():
    """
    Створити новий товар (Валідація даних - Рівень 3)
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            title:
              type: string
            price:
              type: number
    responses:
      201:
        description: Товар створено
      400:
        description: Помилка валідації
    """
    data = request.get_json(silent=True)
    if not data or 'title' not in data or 'price' not in data:
        return jsonify({'error': 'Потрібні поля: title та price'}), 400
    if not isinstance(data['title'], str) or not isinstance(data['price'], (int, float)):
        return jsonify({'error': 'title має бути рядком, а price - числом'}), 400

    db = get_db()
    cursor = db.execute('INSERT INTO products (title, price) VALUES (?, ?)', (data['title'], data['price']))
    db.commit()
    return jsonify({'id': cursor.lastrowid, 'title': data['title'], 'price': data['price']}), 201


@app.route('/api/v1/products/<int:product_id>', methods=['PUT'])
def api_update_product(product_id):
    """
    Оновити існуючий товар
    ---
    parameters:
      - name: product_id
        in: path
        type: integer
        required: true
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            title:
              type: string
            price:
              type: number
    responses:
      200:
        description: Товар оновлено
      404:
        description: Товар не знайдено
      400:
        description: Помилка валідації
    """
    db = get_db()
    row = db.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if row is None:
        return jsonify({'error': 'Товар не знайдено'}), 404

    data = request.get_json(silent=True)
    if not data or 'title' not in data or 'price' not in data:
        return jsonify({'error': 'Потрібні поля: title та price'}), 400

    db.execute('UPDATE products SET title = ?, price = ? WHERE id = ?', (data['title'], data['price'], product_id))
    db.commit()
    return jsonify({'id': product_id, 'title': data['title'], 'price': data['price']}), 200


@app.route('/api/v1/products/<int:product_id>', methods=['DELETE'])
def api_delete_product(product_id):
    """
    Видалити товар
    ---
    parameters:
      - name: product_id
        in: path
        type: integer
        required: true
    responses:
      204:
        description: Товар успішно видалено
      404:
        description: Товар не знайдено
    """
    db = get_db()
    row = db.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if row is None:
        return jsonify({'error': 'Товар не знайдено'}), 404

    db.execute('DELETE FROM products WHERE id = ?', (product_id,))
    db.commit()
    return '', 204


@app.route('/api/v1/clients', methods=['GET'])
def api_get_clients():
    """
    Отримати список клієнтів
    ---
    responses:
      200:
        description: Список клієнтів
    """
    db = get_db()
    rows = db.execute('SELECT * FROM clients').fetchall()
    return jsonify([dict(row) for row in rows]), 200


@app.route('/api/v1/orders', methods=['GET'])
def api_get_orders():
    """
    Отримати список замовлень
    ---
    responses:
      200:
        description: Список замовлень
    """
    db = get_db()
    rows = db.execute('SELECT * FROM orders').fetchall()
    return jsonify([dict(row) for row in rows]), 200


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)
