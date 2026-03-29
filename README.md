# EV Concierge — Property Manager Webapp

A Django-based property management dashboard for vacation rental managers. Built with **UV** package manager and **Django 6.x**.

## Features

- 🏠 **Property Management** — Create and manage properties with photos, house rules, WiFi info, check-in/out times
- 📁 **Categories & Services** — Configure service categories (Food & Drinks, Experiences, Wellness, etc.) with items, prices, and photos
- 📅 **Booking Management** — Set guest access dates, view uploaded documents (ID/passport), track expenses
- 🛒 **Order Management** — View incoming orders, confirm/decline/fulfill with quick-action buttons
- 🔔 **Push Notifications** — Compose, schedule, and target notifications to all guests or specific bookings
- 💬 **Chat Overview** — View AI conversations, respond to escalated chats from guests
- ⭐ **Specials & Promotions** — Feature items on the guest home screen, link to push notifications

---

## Prerequisites

- **Python 3.12+** — Check with `python3 --version`
- **Git** — To clone the repository

---

## Installation

### Step 1: Install UV (Python package manager)

UV is a fast Python package manager by Astral. Install it with:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After installation, add UV to your PATH:

```bash
# For the current session:
source $HOME/.local/bin/env

# Or add this line to your ~/.bashrc or ~/.zshrc for permanent access:
export PATH="$HOME/.local/bin:$PATH"
```

Verify the installation:

```bash
uv --version
# Should output something like: uv 0.11.x
```

### Step 2: Clone the repository

```bash
git clone https://github.com/montemurroPaolo/EVConcierge.git
cd EVConcierge
```

### Step 3: Install dependencies

UV reads the `pyproject.toml` and installs all dependencies (Django, Pillow) into an isolated virtual environment automatically:

```bash
uv sync
```

This will:
- Create a `.venv/` directory with a Python virtual environment
- Install Django 6.x, Pillow, and all transitive dependencies
- Lock versions in `uv.lock`

### Step 4: Run database migrations

```bash
uv run python manage.py migrate
```

This creates the SQLite database (`db.sqlite3`) and sets up all 12 tables.

### Step 5: Create a superuser (admin account)

```bash
uv run python manage.py createsuperuser
```

You'll be prompted for:
- **Username** — e.g. `admin`
- **Email** — e.g. `admin@example.com`
- **Password** — choose a secure password

### Step 6: Start the development server

```bash
uv run python manage.py runserver
```

The app will be available at **http://localhost:8000/**

---

## Usage

| URL | Description |
|-----|-------------|
| http://localhost:8000/ | Dashboard (requires login) |
| http://localhost:8000/accounts/login/ | Login page |
| http://localhost:8000/admin/ | Django admin panel |
| http://localhost:8000/properties/ | Property management |
| http://localhost:8000/bookings/ | Booking management |
| http://localhost:8000/orders/ | Order management |
| http://localhost:8000/notifications/ | Push notifications |
| http://localhost:8000/chat/ | Chat overview |
| http://localhost:8000/specials/ | Specials & promotions |

---

## Common UV Commands

```bash
# Install dependencies
uv sync

# Add a new dependency
uv add <package-name>

# Run any Django management command
uv run python manage.py <command>

# Examples:
uv run python manage.py makemigrations    # Create new migrations
uv run python manage.py migrate           # Apply migrations
uv run python manage.py createsuperuser   # Create admin user
uv run python manage.py runserver         # Start dev server
uv run python manage.py shell             # Django shell
uv run python manage.py test              # Run tests
```

---

## Project Structure

```
EVConcierge/                    # Django project config
├── settings.py
├── urls.py
├── wsgi.py / asgi.py

property_manager/               # Main application
├── models.py                   # 12 data models
├── admin.py                    # Customized Django admin
├── forms.py                    # All forms & formsets
├── views.py                    # 20+ dashboard views
├── urls.py                     # URL routing
├── templates/                  # HTML templates
├── static/                     # CSS & JavaScript
├── templatetags/               # Custom template filters
└── migrations/                 # Database migrations

manage.py                       # Django management script
pyproject.toml                  # UV project config & dependencies
uv.lock                         # Locked dependency versions
```

---

## Tech Stack

- **UV** — Python package manager
- **Python 3.12**
- **Django 6.x** — Web framework
- **Pillow** — Image handling (property photos, guest documents)
- **SQLite** — Database (development)
