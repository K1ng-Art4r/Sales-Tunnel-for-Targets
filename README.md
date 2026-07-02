# Sales Tunnel for Targets

Telegram bot for automating sales funnels, lead qualification, onboarding, and customer engagement.

## Overview

Sales Tunnel for Targets is a production-ready Telegram bot developed for the Aivel ecosystem. It automates user onboarding, calculates business savings, evaluates potential deals, schedules meetings, synchronizes data with Google Sheets, and manages customer follow-up scenarios.

## My Role

I was responsible for the entire backend development:

- Designed the application architecture
- Developed all Telegram bot scenarios using Aiogram
- Implemented FSM-based user flows
- Built PostgreSQL data layer
- Integrated Google Sheets API
- Implemented Calendly integration
- Developed business logic for savings and deal evaluation
- Configured Docker deployment

## Tech Stack

- Python
- Aiogram
- PostgreSQL
- Docker
- Google Sheets API
- Calendly API

## Features

- User onboarding
- Sales funnel automation
- Savings calculator
- Deal evaluation
- Meeting scheduling
- Google Sheets synchronization
- User export
- Warm-up messaging
- Finite State Machine (FSM)
- Docker deployment

## Architecture

```
main.py
│
├── Telegram Bot
├── Business Logic
├── PostgreSQL
├── Google Sheets API
├── Calendly
└── Background Services
```

## Project Structure

```
app/
handlers/
db.py
events.py
export_sync.py
warmup.py
states.py
scoring.py
keyboards.py
config.py
```

## Screenshots

> Screenshots will be added soon.

## Installation

```bash
git clone https://github.com/K1ng-Art4r/Sales-Tunnel-for-Targets.git

cd Sales-Tunnel-for-Targets

python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt
```

Create `.env`

```env
BOT_TOKEN=...
DATABASE_URL=...
...
```

Run

```bash
python main.py
```

## Docker

```bash
docker build -t sales-tunnel-bot .

docker run --env-file .env sales-tunnel-bot
```

## Repository Status

This repository represents a portfolio version of a commercial project.

Some confidential business logic and production credentials have been removed.

## Author

Backend Development — K1ng-Art4r
