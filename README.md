# 🐟 FishMarket – Multi-Seller Fish Marketplace

A Python/Flask web platform where sellers register fish shops and customers browse & order online.

## Quick Start

```bash
cd fishmarket
pip install -r requirements.txt
python app.py
```
Visit: **http://127.0.0.1:5000**

---

## Seed Accounts (auto-created on first run)

| Role     | Email                       | Password      |
|----------|-----------------------------|---------------|
| Admin    | admin@fishmarket.com        | admin1234     |
| Seller   | seller@example.com          | seller1234    |
| Customer | customer@example.com        | customer1234  |

---

## Architecture

```
fishmarket/
├── app.py                      # Main Flask app + models + routes
├── requirements.txt
├── fishmarket.db               # SQLite DB (auto-created)
└── templates/
    ├── base.html               # Shared layout & design system
    ├── index.html              # Homepage
    ├── shops.html              # Shop listing + search
    ├── shop_detail.html        # Single shop + fish list
    ├── fish_detail.html        # Single fish page
    ├── register.html / login.html
    ├── seller/
    │   ├── dashboard.html      # Seller control panel
    │   ├── shop_form.html      # Create/edit shop
    │   ├── fish_form.html      # Add/edit fish listing
    │   └── orders.html         # Incoming orders management
    ├── customer/
    │   ├── order_form.html     # Place an order
    │   └── my_orders.html      # Order history + cancel
    ├── admin/
    │   ├── dashboard.html      # Admin overview
    │   ├── users.html          # ⚠️ PII – all user data
    │   ├── shops.html          # All shops
    │   └── orders.html         # All orders
    └── errors/403.html, 404.html
```

---

## Roles & Permissions

| Feature                          | Public | Customer | Seller | Admin |
|----------------------------------|--------|----------|--------|-------|
| Browse shops & fish              | ✅     | ✅       | ✅     | ✅    |
| Register / Login                 | ✅     | —        | —      | —     |
| Place & cancel orders            | ❌     | ✅       | ❌     | ❌    |
| Create/edit shop                 | ❌     | ❌       | ✅     | ❌    |
| Add/edit/delete fish listings    | ❌     | ❌       | ✅     | ❌    |
| Manage incoming orders           | ❌     | ❌       | ✅     | ❌    |
| **View PII (email/phone/address)**| ❌    | ❌       | ❌     | ✅    |
| Activate/suspend accounts        | ❌     | ❌       | ❌     | ✅    |
| View all orders/shops platform-wide| ❌  | ❌       | ❌     | ✅    |

---

## Business Constraints

- A seller may have **only one shop**.
- A fish is *orderable* only if **all three** are true: `is_orderable=True`, `stock_kg > 0`, and `shop.is_open=True`.
- Placing an order **deducts stock**; cancelling a pending order **restores stock**.
- Sellers can update order status: `pending → confirmed → ready → delivered → cancelled`.
- Customers can only cancel **pending** orders.
- Admin cannot be suspended by other admins.
- Passwords are stored as **bcrypt hashes** (via Werkzeug).

---

## Security Notes (Production Checklist)

- [ ] Set `SECRET_KEY` from environment variable, not hardcoded
- [ ] Switch from SQLite to PostgreSQL/MySQL
- [ ] Enable HTTPS (TLS)
- [ ] Add CSRF protection (`flask-wtf`)
- [ ] Rate-limit login endpoint
- [ ] Add email verification for new accounts
- [ ] Audit log for admin PII access
