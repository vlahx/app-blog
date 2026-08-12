from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
import sqlite3

from app.core.config import PROJECT_ROOT

logger = logging.getLogger(__name__)
DB_PATH = PROJECT_ROOT / "db" / "app.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_minishop_db() -> None:
    # Creeaza tabelele necesare pentru modulul Minishop.
    with _get_conn() as conn:
        cursor = conn.cursor()
        
        # 1. Categorii produse
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            slug VARCHAR(120) NOT NULL UNIQUE,
            description TEXT,
            icon VARCHAR(50) DEFAULT '📦',
            created_at DATETIME NOT NULL
        )
        ''')

        # 2. Produse
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            title VARCHAR(200) NOT NULL,
            slug VARCHAR(220) NOT NULL UNIQUE,
            description_html TEXT,
            short_description TEXT,
            price REAL NOT NULL DEFAULT 0.0,
            currency VARCHAR(10) DEFAULT 'RON',
            product_type VARCHAR(20) DEFAULT 'physical',
            digital_file_url TEXT,
            stock_quantity INTEGER DEFAULT 100,
            is_active BOOLEAN DEFAULT 1,
            featured_image TEXT,
            gallery_images_json TEXT,
            video_url TEXT,
            created_at DATETIME NOT NULL,
            FOREIGN KEY (category_id) REFERENCES shop_categories (id) ON DELETE SET NULL
        )
        ''')

        # 3. Comenzi
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number VARCHAR(50) NOT NULL UNIQUE,
            user_id INTEGER,
            customer_name VARCHAR(150) NOT NULL,
            customer_email VARCHAR(150) NOT NULL,
            customer_phone VARCHAR(50),
            shipping_address TEXT,
            total_amount REAL NOT NULL,
            currency VARCHAR(10) DEFAULT 'RON',
            payment_method VARCHAR(30) NOT NULL,
            payment_status VARCHAR(30) DEFAULT 'pending',
            fulfillment_status VARCHAR(30) DEFAULT 'processing',
            stripe_session_id VARCHAR(255),
            download_token VARCHAR(100),
            download_count INTEGER DEFAULT 0,
            created_at DATETIME NOT NULL
        )
        ''')

        # 4. Articole Comanda
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_title VARCHAR(200) NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES shop_orders (id) ON DELETE CASCADE
        )
        ''')

        # 5. Recenzii / Reviews & Stele (1-5)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            user_id INTEGER,
            user_name VARCHAR(150) NOT NULL,
            user_avatar TEXT,
            rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
            comment TEXT NOT NULL,
            is_approved BOOLEAN DEFAULT 1,
            created_at DATETIME NOT NULL,
            FOREIGN KEY (product_id) REFERENCES shop_products (id) ON DELETE CASCADE
        )
        ''')
        conn.commit()


# --- CATEGORIES CRUD ---

def list_shop_categories() -> list[dict]:
    init_minishop_db()
    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM shop_categories ORDER BY name ASC")
        return [dict(r) for r in cursor.fetchall()]


def save_shop_category(name: str, slug: str, description: str = "", icon: str = "📦", cat_id: int | None = None) -> int:
    init_minishop_db()
    now = datetime.now(timezone.utc)
    with _get_conn() as conn:
        cursor = conn.cursor()
        if cat_id:
            cursor.execute(
                "UPDATE shop_categories SET name=?, slug=?, description=?, icon=? WHERE id=?",
                (name, slug, description, icon, cat_id)
            )
            conn.commit()
            return cat_id
        else:
            cursor.execute(
                "INSERT INTO shop_categories (name, slug, description, icon, created_at) VALUES (?, ?, ?, ?, ?)",
                (name, slug, description, icon, now)
            )
            conn.commit()
            return cursor.lastrowid


def delete_shop_category(cat_id: int) -> bool:
    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shop_categories WHERE id=?", (cat_id,))
        conn.commit()
        return cursor.rowcount > 0


# --- PRODUCTS CRUD ---

def list_shop_products(category_slug: str | None = None, active_only: bool = True) -> list[dict]:
    init_minishop_db()
    with _get_conn() as conn:
        cursor = conn.cursor()
        sql = "SELECT p.*, c.name as category_name, c.slug as category_slug FROM shop_products p LEFT JOIN shop_categories c ON p.category_id = c.id WHERE 1=1"
        params = []
        if active_only:
            sql += " AND p.is_active = 1"
        if category_slug:
            sql += " AND c.slug = ?"
            params.append(category_slug)
        sql += " ORDER BY p.id DESC"
        cursor.execute(sql, params)
        rows = [dict(r) for r in cursor.fetchall()]
        for r in rows:
            if r.get("gallery_images_json"):
                try:
                    r["gallery_images"] = json.loads(r["gallery_images_json"])
                except Exception:
                    r["gallery_images"] = []
            else:
                r["gallery_images"] = []
        return rows


def get_shop_product(val: str | int) -> dict | None:
    init_minishop_db()
    with _get_conn() as conn:
        cursor = conn.cursor()
        if isinstance(val, int) or (isinstance(val, str) and val.isdigit()):
            cursor.execute("SELECT p.*, c.name as category_name, c.slug as category_slug FROM shop_products p LEFT JOIN shop_categories c ON p.category_id = c.id WHERE p.id = ?", (int(val),))
        else:
            cursor.execute("SELECT p.*, c.name as category_name, c.slug as category_slug FROM shop_products p LEFT JOIN shop_categories c ON p.category_id = c.id WHERE p.slug = ?", (str(val),))
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        if res.get("gallery_images_json"):
            try:
                res["gallery_images"] = json.loads(res["gallery_images_json"])
            except Exception:
                res["gallery_images"] = []
        else:
            res["gallery_images"] = []
        return res


def save_shop_product(data: dict) -> int:
    init_minishop_db()
    now = datetime.now(timezone.utc)
    gallery_json = json.dumps(data.get("gallery_images", []))
    with _get_conn() as conn:
        cursor = conn.cursor()
        prod_id = data.get("id")
        if prod_id:
            cursor.execute('''
            UPDATE shop_products SET
                category_id=?, title=?, slug=?, description_html=?, short_description=?,
                price=?, currency=?, product_type=?, digital_file_url=?, stock_quantity=?,
                is_active=?, featured_image=?, gallery_images_json=?, video_url=?
            WHERE id=?
            ''', (
                data.get("category_id"), data["title"], data["slug"], data.get("description_html", ""),
                data.get("short_description", ""), float(data.get("price", 0)), data.get("currency", "RON"),
                data.get("product_type", "physical"), data.get("digital_file_url"), int(data.get("stock_quantity", 100)),
                1 if data.get("is_active", True) else 0, data.get("featured_image"), gallery_json,
                data.get("video_url"), prod_id
            ))
            conn.commit()
            return int(prod_id)
        else:
            cursor.execute('''
            INSERT INTO shop_products (
                category_id, title, slug, description_html, short_description, price, currency,
                product_type, digital_file_url, stock_quantity, is_active, featured_image,
                gallery_images_json, video_url, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get("category_id"), data["title"], data["slug"], data.get("description_html", ""),
                data.get("short_description", ""), float(data.get("price", 0)), data.get("currency", "RON"),
                data.get("product_type", "physical"), data.get("digital_file_url"), int(data.get("stock_quantity", 100)),
                1 if data.get("is_active", True) else 0, data.get("featured_image"), gallery_json,
                data.get("video_url"), now
            ))
            conn.commit()
            return cursor.lastrowid


def delete_shop_product(prod_id: int) -> bool:
    import shutil
    product = get_shop_product(prod_id)
    if product and product.get("slug"):
        slug = product["slug"]
        prod_dir = PROJECT_ROOT / "static" / "uploads" / "shop" / slug
        if prod_dir.is_dir():
            try:
                shutil.rmtree(prod_dir)
            except Exception as e:
                logger.warning(f"Error removing product directory {prod_dir}: {e}")
                
        imgs_to_clean = []
        if product.get("featured_image"):
            imgs_to_clean.append(product["featured_image"])
        if product.get("gallery_images"):
            imgs_to_clean.extend(product["gallery_images"])
            
        for img_url in imgs_to_clean:
            if img_url and img_url.startswith("/static/uploads/shop/"):
                rel_p = img_url.lstrip("/")
                p_file = PROJECT_ROOT / rel_p
                if p_file.is_file():
                    try:
                        p_file.unlink()
                    except Exception:
                        pass

    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shop_products WHERE id=?", (prod_id,))
        conn.commit()
        return cursor.rowcount > 0


# --- ORDERS CRUD ---

def create_shop_order(order_data: dict, items: list[dict]) -> dict:
    init_minishop_db()
    now = datetime.now(timezone.utc)
    import uuid
    order_num = f"TRK-{uuid.uuid4().hex[:8].upper()}"
    token = uuid.uuid4().hex
    
    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO shop_orders (
            order_number, user_id, customer_name, customer_email, customer_phone,
            shipping_address, total_amount, currency, payment_method, payment_status,
            fulfillment_status, stripe_session_id, download_token, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_num, order_data.get("user_id"), order_data["customer_name"],
            order_data["customer_email"], order_data.get("customer_phone"),
            order_data.get("shipping_address"), float(order_data["total_amount"]),
            order_data.get("currency", "RON"), order_data["payment_method"],
            order_data.get("payment_status", "pending"),
            order_data.get("fulfillment_status", "processing"),
            order_data.get("stripe_session_id"), token, now
        ))
        order_id = cursor.lastrowid
        
        for item in items:
            cursor.execute('''
            INSERT INTO shop_order_items (order_id, product_id, product_title, quantity, unit_price)
            VALUES (?, ?, ?, ?, ?)
            ''', (order_id, item.get("product_id"), item["product_title"], int(item.get("quantity", 1)), float(item["unit_price"])))
        
        conn.commit()
        
    return get_shop_order(order_num)


def get_shop_order(val: str | int) -> dict | None:
    init_minishop_db()
    with _get_conn() as conn:
        cursor = conn.cursor()
        if isinstance(val, int) or (isinstance(val, str) and val.isdigit()):
            cursor.execute("SELECT * FROM shop_orders WHERE id=?", (int(val),))
        else:
            cursor.execute("SELECT * FROM shop_orders WHERE order_number=? OR download_token=?", (str(val), str(val)))
        row = cursor.fetchone()
        if not row:
            return None
        order = dict(row)
        cursor.execute("SELECT * FROM shop_order_items WHERE order_id=?", (order["id"],))
        order["items"] = [dict(i) for i in cursor.fetchall()]
        order["order_items"] = order["items"]
        return order


def list_shop_orders(status: str | None = None) -> list[dict]:
    init_minishop_db()
    with _get_conn() as conn:
        cursor = conn.cursor()
        sql = "SELECT * FROM shop_orders WHERE 1=1"
        params = []
        if status:
            sql += " AND (payment_status=? OR fulfillment_status=?)"
            params.extend([status, status])
        sql += " ORDER BY id DESC"
        cursor.execute(sql, params)
        orders = [dict(r) for r in cursor.fetchall()]
        for o in orders:
            cursor.execute("SELECT * FROM shop_order_items WHERE order_id=?", (o["id"],))
            o["items"] = [dict(i) for i in cursor.fetchall()]
            o["order_items"] = o["items"]
        return orders


def update_order_status(order_id: int, payment_status: str | None = None, fulfillment_status: str | None = None) -> bool:
    with _get_conn() as conn:
        cursor = conn.cursor()
        updates = []
        params = []
        if payment_status:
            updates.append("payment_status=?")
            params.append(payment_status)
        if fulfillment_status:
            updates.append("fulfillment_status=?")
            params.append(fulfillment_status)
        if not updates:
            return False
        params.append(order_id)
        sql = f"UPDATE shop_orders SET {', '.join(updates)} WHERE id=?"
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount > 0


# --- REVIEWS & RATINGS CRUD ---

def add_shop_review(product_id: int, user_id: int | None, user_name: str, user_avatar: str | None, rating: int, comment: str) -> int:
    init_minishop_db()
    now = datetime.now(timezone.utc)
    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO shop_reviews (product_id, user_id, user_name, user_avatar, rating, comment, is_approved, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        ''', (product_id, user_id, user_name, user_avatar, rating, comment, now))
        conn.commit()
        return cursor.lastrowid


def list_product_reviews(product_id: int, approved_only: bool = True) -> list[dict]:
    init_minishop_db()
    with _get_conn() as conn:
        cursor = conn.cursor()
        sql = "SELECT * FROM shop_reviews WHERE product_id = ?"
        params = [product_id]
        if approved_only:
            sql += " AND is_approved = 1"
        sql += " ORDER BY id DESC"
        cursor.execute(sql, params)
        return [dict(r) for r in cursor.fetchall()]


def get_product_rating_summary(product_id: int) -> dict:
    init_minishop_db()
    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt, AVG(rating) as avg_rating FROM shop_reviews WHERE product_id=? AND is_approved=1", (product_id,))
        row = cursor.fetchone()
        cnt = row["cnt"] if row and row["cnt"] else 0
        avg_val = round(row["avg_rating"], 1) if row and row["avg_rating"] else 0.0
        return {"review_count": cnt, "average_rating": avg_val}

def remove_product_image(product_id: int, image_url: str) -> dict | None:
    init_minishop_db()
    product = get_shop_product(product_id)
    if not product:
        return None
    
    featured = product.get("featured_image")
    gallery = product.get("gallery_images") or []
    
    if featured == image_url:
        if gallery:
            featured = gallery.pop(0)
        else:
            featured = None
    elif image_url in gallery:
        gallery = [img for img in gallery if img != image_url]
        
    product["featured_image"] = featured
    product["gallery_images"] = gallery
    save_shop_product(product)
    
    if image_url and image_url.startswith("/static/uploads/shop/"):
        rel_path = image_url.lstrip("/")
        phys_file = PROJECT_ROOT / rel_path
        if phys_file.is_file():
            try:
                phys_file.unlink()
            except Exception:
                pass
                
    return get_shop_product(product_id)

def set_product_cover_image(product_id: int, image_url: str) -> dict | None:
    init_minishop_db()
    product = get_shop_product(product_id)
    if not product:
        return None
        
    featured = product.get("featured_image")
    gallery = product.get("gallery_images") or []
    
    all_imgs = []
    if featured:
        all_imgs.append(featured)
    all_imgs.extend(gallery)
    all_imgs = list(dict.fromkeys(all_imgs))
    
    if image_url in all_imgs:
        product["featured_image"] = image_url
        product["gallery_images"] = [img for img in all_imgs if img != image_url]
        save_shop_product(product)
        
    return get_shop_product(product_id)


def list_user_orders(user_id: int | None = None, email: str | None = None) -> list[dict]:
    init_minishop_db()
    with get_minishop_db() as conn:
        query = "SELECT * FROM shop_orders WHERE 1=1"
        params = []
        if email and email.strip():
            query += " AND (LOWER(customer_email) = LOWER(?))"
            params.append(email.strip())
        query += " ORDER BY id DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
