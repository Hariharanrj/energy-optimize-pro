# Energy Optimize Pro — AI Smart Grid Management System

> Real-time energy monitoring, AI-driven load optimisation, automated alerts, and live analytics dashboard built with Python.

---

## Features

- **Live energy analytics** — real-time graphs for energy consumption, grid efficiency, and load distribution
- **AI-driven threshold alerts** — automatic detection of overload conditions with configurable thresholds
- **Email alert system** — instant notifications with video evidence captured from webcam
- **Smart grid status** — dynamic OPTIMISING / GREEN ENERGY / OVERLOAD state tracking
- **Serial port integration** — reads live sensor data (temperature, humidity, pulse, SpO2) over COM/USB
- **Export & logging** — full timestamped event log with export to `.txt`
- **Cross-platform UI** — built with Tkinter, runs on Windows / Linux / macOS

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.x |
| GUI | Tkinter + ttk |
| Data Visualisation | Matplotlib (embedded in Tkinter) |
| Serial Communication | PySerial |
| Video Capture | OpenCV (cv2) |
| Email Alerts | smtplib + MIME |
| Audio Alerts | Pygame |
| Data Processing | NumPy, collections.deque |
| Config Storage | JSON |

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/hariharan-ai-ds/energy-optimize-pro.git
cd energy-optimize-pro

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your email credentials as environment variables
#    (never hardcode credentials — use env vars or .env)
export EMAIL_SENDER="your_gmail@gmail.com"
export EMAIL_PASSWORD="your_app_password"
#    On Windows:
#    set EMAIL_SENDER=your_gmail@gmail.com
#    set EMAIL_PASSWORD=your_app_password

# 4. Run the application
python monitor.py
```

---

## Email Setup (Gmail)

1. Enable 2-Factor Authentication on your Google account
2. Go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Generate an **App Password** for "Mail"
4. Use that 16-character password as `EMAIL_PASSWORD` — **never your main Gmail password**

---

## Sensor Data Format

The system reads serial data in this format from an Arduino / microcontroller:

```
TEMP:36.5,HUM:45,PULSE:72,SPO2:98
```

| Field | Unit | Description |
|---|---|---|
| TEMP | °C | Temperature sensor (maps → energy kW) |
| HUM | % | Humidity sensor (maps → grid efficiency %) |
| PULSE | BPM | Heart rate sensor (maps → peak load %) |
| SPO2 | % | Oxygen level (maps → renewable contribution %) |

---

## Project Structure

```
energy-optimize-pro/
├── monitor.py                  # Main application
├── alarm.mp3                   # Alert sound file
├── energy_optimizer_config.json # Saved configuration (auto-generated)
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Screenshots

> Dashboard showing live energy consumption, grid efficiency, and load distribution graphs with the real-time event log.

---

## Security Note

This project uses **environment variables** for email credentials. Never commit passwords or API keys to version control. A `.gitignore` is included to exclude config files with sensitive data.

---

## Author

**Hariharan J**
B.Tech — Artificial Intelligence & Data Science
P.S.R.R College of Engineering, Sivakasi

- Email: rjhariharan2004@gmail.com
- LinkedIn: [linkedin.com/in/hariharan-ai-ds](https://www.linkedin.com/in/hariharan-ai-ds)

---

## License

MIT License — free to use, modify, and distribute with attribution.
