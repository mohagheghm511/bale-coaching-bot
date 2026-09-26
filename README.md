<div align="center">

# 🧠 Coaching Bot for Bale: Psychology Courses, Session Booking & Personality Tests

**A complete business bot on the [Bale](https://bale.ai) messenger for a psychology and coaching practice.** It sells courses, books coaching sessions, runs psychometric tests with automatic analysis, and handles payments and installments.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Bale](https://img.shields.io/badge/Bale-python--bale--bot-00A884)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)

</div>

---

## ✨ Features

### 👤 For clients
- **Onboarding:** name and phone number shared through the contact button.
- **🧪 "Personality black box":** psychometric tests with weighted questions, score ranges, **automatic result analysis** and per-question analysis. Access to each test can be restricted.
- **📅 Coaching session booking:** coaching packages, time slots with capacity, session types (in-person/online), rescheduling and cancellation.
- **🎓 Courses & trainings** with limited capacity and sold-count tracking.
- **💳 Payments:** native **Bale payments** or card-to-card with receipt upload and approval.
- **Installment plans** with a "my installments" view and reminders.
- **Discount codes.**
- 🎧 Podcasts, 👤 "About me", ⭐ client reviews (moderated), ❓ FAQ, 📞 support. All content pages are editable (text, image, audio, video).
- Profile.

### 🛠️ Admin panel (inside Bale)
- A dashboard with users, pending payments, active reservations, total income, tests taken and pending reviews.
- Payment approval, reservation management (reschedule or cancel), time slots and packages.
- A test builder (questions, options, weights, score ranges, analysis texts).
- Products, discounts, installment plans, reviews moderation, static content editor, **broadcasts**.
- Multiple admins.

### ⏰ Automation
An APScheduler job sends session reminders and installment due-date notices.

## 🧰 Tech Stack
Python · python-bale-bot · SQLAlchemy 2 · SQLite · APScheduler · pydantic-settings · jdatetime · Docker

## 🚀 Getting Started
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env     # bot token, payment token, admin IDs
python main.py
```
Or with Docker:
```bash
docker build -t coaching-bot backend
docker run --env-file backend/.env coaching-bot
```
The database and all tables are created **empty on first run**, and lightweight migrations run automatically.

| Variable | Description |
|---|---|
| `BALE_BOT_TOKEN` | Bot token from Bale's BotFather |
| `BALE_PAYMENT_TOKEN` | Bale payment provider token |
| `ADMIN_BALE_IDS` | Comma-separated numeric Bale IDs of admins |
| `DATABASE_URL` | Defaults to `sqlite:///./coaching_bot.db` |

## 📁 Project Structure
```
backend/
├── main.py              # entry point, migrations, bot events
├── bot/handlers/        # start, products, reservation, tests, payment, installment, support, profile, static pages, admin
├── models/              # user, product/reservation, payment, test, review, discount, installment, static content
├── services/scheduler.py
├── api/routes/          # REST route modules (FastAPI) for an external admin panel
└── core/                # config, database, bot instance
```

---
<div align="center">Built by <a href="https://github.com/mohagheghm511">@mohagheghm511</a></div>
