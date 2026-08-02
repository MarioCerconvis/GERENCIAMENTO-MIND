# Project Setup & Requirements: Gerenciamento-MIND

## Overview
This project is a web-based Kanban and project management application built with Python.

## Core Frameworks & Libraries
- **Language**: Python 3.x
- **Web Framework**: [Flask](https://flask.palletsprojects.com/) (>=3.0.0)
- **Database ORM**: Flask-SQLAlchemy (>=3.1.0)
- **Database Drivers**: PyMySQL (>=1.1.0) for MySQL, SQLite (default for development)
- **Security & Authentication**: Flask-Bcrypt (>=1.0.1) for password hashing
- **Task Scheduling**: APScheduler (>=3.10.0) used for background tasks (e.g., SLA checking)
- **Environment Management**: python-dotenv (>=1.0.0)

## Frontend Stack
- **HTML/CSS/JS**: Standard Web Technologies (HTML5, CSS, Vanilla JS)
- **Template Engine**: Jinja2 (integrated with Flask)

## Environment Configuration
The project relies on environment variables for configuration. You need a `.env` file in the root directory. Use `.env.example` as a template.

**Key Environment Variables:**
- `SECRET_KEY`: Flask secret key for secure sessions.
- `DATABASE_URL`: Connection string for the database (e.g., `sqlite:///gerenciamento.db` or `mysql+pymysql://...`).
- `EMAIL_ATIVO`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_REMETENTE`: Email configuration settings.
- `SLA_CHECK_HOUR`, `SLA_CHECK_MINUTE`: SLA Scheduler background task configuration.

## How to Run Locally

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone <repository-url>
   cd gerenciamento-mind
   ```

2. **Set up a Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Linux/Mac
   # venv\Scripts\activate   # On Windows
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure the Environment**:
   Copy the example environment file and configure it with your settings:
   ```bash
   cp .env.example .env
   ```

5. **Initialize the Database**:
   The application uses Flask-SQLAlchemy and creates tables automatically on first run (`db.create_all()` in `app.py`). 
   To populate the database with initial configurations or test data, you can use the seed script:
   ```bash
   python seed_data.py
   ```
   *(Note: Additional scripts like `migrate_to_objects.py` are available for migrating from previous system architectures).*

6. **Run the Application**:
   You can run the application directly via Python or Flask:
   ```bash
   python app.py
   # OR
   flask run
   ```