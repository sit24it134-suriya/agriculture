# Farmers Market Web App

A Flask-based online marketplace for farm products, built with SQLite and server-side rendering. The app supports customer shopping, farmer product submissions, and admin approval workflows.

## Features

- Public product browsing and product detail pages
- Customer cart and checkout flow
- Role-based access:
  - `customer` for shopping
  - `farmer` for adding products
  - `master` for admin approval and order management
- Farmer product approval pipeline
- Order management and order history
- JSON API endpoints for products and cart interactions
- Seeded sample data with default users and products

## Project Structure

- `app.py` - Main Flask application and database models
- `init_db.py` - Helper script to initialize the SQLite database
- `requirements.txt` - Python package dependencies
- `templates/` - HTML templates for pages
- `static/` - Static CSS and JavaScript assets
- `database.db` - SQLite database file generated at runtime

## Requirements

- Python 3.11+ (or compatible Python 3.x)
- Flask
- Flask-SQLAlchemy
- Werkzeug

Install dependencies:

```bash
pip install -r requirements.txt
```

## Setup

1. Clone or copy the project to your local machine.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Initialize the database:

```bash
python init_db.py
```

Alternatively, you can use the Flask CLI command:

```bash
flask initdb
```

The app also initializes the database automatically when starting if `database.db` does not exist.

## Run the App

Start the application:

```bash
python app.py
```

Then open your browser at `http://127.0.0.1:5000`.

## Environment

Optional environment variables:

- `FLASK_SECRET_KEY` - secret key used by Flask sessions.
- `LOG_LEVEL` - logging level for application output (default: `INFO`).

If `FLASK_SECRET_KEY` is not set, the app uses the default key: `farmersmarketsecret`.

Logs are written to `logs/app.log` in the project root.

## Default Sample Accounts

The seeded database includes sample user accounts:

- Admin / Master
  - Email: `admin@example.com`
  - Password: `admin123`
  - Role: `master`

- Farmer
  - Email: `farmer1@example.com`
  - Password: `farm123`
  - Role: `farmer`

- Customer
  - Email: `customer@example.com`
  - Password: `shop123`
  - Role: `customer`

## Usage

- Browse products on the home page or products page.
- Sign up or log in to add products to cart and checkout.
- Farmers can sign up with the `farmer` role and submit products for approval.
- Master admin can approve farmers, review new products, and update order status via the admin dashboard.

## API Endpoints

The application exposes simple JSON endpoints:

- `GET /api/products` - List approved products, or all products for master admin.
- `GET /api/cart` - View current user cart.
- `POST /api/remove-cart-item` - Remove an item from cart.
- `POST /api/update-cart-quantity` - Update cart item quantity.
- `GET /api/featured-products` - Fetch recent featured products.

## Notes

- The database is SQLite-based and stored in `database.db`.
- The project is designed for demo and learning purposes; it is not production hardened.
- To reset the database and sample data, delete `database.db` and run `python init_db.py` again.

## License

This project is provided as-is for educational/demo use.
