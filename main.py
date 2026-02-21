"""
Telegram Weather Bot - Daily weather report for Gebze and Istanbul.
Sends yesterday's summary and tomorrow's forecast at 20:00 Turkey time.
"""

import os
import sys
from datetime import datetime, timedelta

import requests
from telegram import Bot

# OpenWeather One Call API 3.0 base URLs
ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"
DAY_SUMMARY_URL = "https://api.openweathermap.org/data/3.0/onecall/day_summary"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Cities: (name, lat, lon)
CITIES = [
    ("Gebze", 40.8028, 29.4307),
    ("İstanbul", 41.0082, 28.9784),
]

# Turkey timezone offset (UTC+3)
TZ_TURKEY = "+03:00"


def log(msg: str) -> None:
    print(msg, flush=True)


def get_yesterday_date_turkey() -> str:
    """Return yesterday's date in YYYY-MM-DD (Turkey time)."""
    # Use UTC+3 for Turkey
    now = datetime.utcnow() + timedelta(hours=3)
    yesterday = now - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def fetch_yesterday_weather(lat: float, lon: float, api_key: str, date: str) -> dict | None:
    """Fetch yesterday's weather via day_summary endpoint."""
    params = {
        "lat": lat,
        "lon": lon,
        "date": date,
        "units": "metric",
        "lang": "tr",
        "tz": TZ_TURKEY,
        "appid": api_key,
    }
    try:
        r = requests.get(DAY_SUMMARY_URL, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        body = (e.response.text or "")[:300] if e.response is not None else ""
        log(f"day_summary HTTP error: {e}; response={body}")
        return None
    except requests.RequestException as e:
        log(f"day_summary API error: {e}")
        return None
    except ValueError as e:
        log(f"day_summary parse error: {e}")
        return None


def fetch_tomorrow_forecast(lat: float, lon: float, api_key: str) -> dict | None:
    """Fetch forecast via onecall, return daily[1] (tomorrow)."""
    params = {
        "lat": lat,
        "lon": lon,
        "exclude": "minutely,hourly",
        "units": "metric",
        "lang": "tr",
        "appid": api_key,
    }
    try:
        r = requests.get(ONECALL_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        daily = data.get("daily", [])
        if len(daily) < 2:
            log("onecall: insufficient daily forecast")
            return None
        return daily[1]
    except requests.HTTPError as e:
        body = (e.response.text or "")[:300] if e.response is not None else ""
        log(f"onecall HTTP error: {e}; response={body}")
        return None
    except requests.RequestException as e:
        log(f"onecall API error: {e}")
        return None
    except (ValueError, KeyError) as e:
        log(f"onecall parse error: {e}")
        return None


def fetch_open_meteo_yesterday(lat: float, lon: float, date: str) -> dict | None:
    """Fallback: fetch yesterday summary from Open-Meteo archive API."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date,
        "end_date": date,
        "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum",
        "timezone": "Europe/Istanbul",
    }
    try:
        r = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=15)
        r.raise_for_status()
        payload = r.json()
        daily = payload.get("daily", {})
        if not isinstance(daily, dict):
            return None
        tmin = (daily.get("temperature_2m_min") or [None])[0]
        tmax = (daily.get("temperature_2m_max") or [None])[0]
        precip = (daily.get("precipitation_sum") or [0])[0]
        if tmin is None and tmax is None:
            return None
        return {
            "temperature": {"min": tmin, "max": tmax},
            "precipitation": {"total": precip or 0},
            "source": "open-meteo",
        }
    except (requests.RequestException, ValueError, IndexError) as e:
        log(f"open-meteo archive error: {e}")
        return None


def fetch_open_meteo_tomorrow(lat: float, lon: float) -> dict | None:
    """Fallback: fetch tomorrow forecast from Open-Meteo forecast API."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_min,temperature_2m_max,weathercode,precipitation_sum",
        "forecast_days": 2,
        "timezone": "Europe/Istanbul",
    }
    weather_map = {
        0: "açık",
        1: "çoğunlukla açık",
        2: "parçalı bulutlu",
        3: "kapalı",
        45: "sisli",
        48: "kırağılı sis",
        51: "hafif çiseleme",
        53: "çiseleme",
        55: "yoğun çiseleme",
        61: "hafif yağmur",
        63: "yağmur",
        65: "kuvvetli yağmur",
        71: "hafif kar",
        73: "kar",
        75: "yoğun kar",
        80: "sağanak",
        81: "kuvvetli sağanak",
        82: "şiddetli sağanak",
        95: "gök gürültülü sağanak",
    }
    try:
        r = requests.get(OPEN_METEO_FORECAST_URL, params=params, timeout=15)
        r.raise_for_status()
        payload = r.json()
        daily = payload.get("daily", {})
        if not isinstance(daily, dict):
            return None
        tmin = (daily.get("temperature_2m_min") or [None, None])[1]
        tmax = (daily.get("temperature_2m_max") or [None, None])[1]
        code = (daily.get("weathercode") or [None, None])[1]
        precip = (daily.get("precipitation_sum") or [0, 0])[1]
        if tmin is None and tmax is None:
            return None
        return {
            "temp": {"min": tmin, "max": tmax},
            "weather": [{"description": weather_map.get(code, "—"), "id": 500 if (precip or 0) > 0 else 800}],
            "rain": {"1h": precip or 0} if (precip or 0) > 0 else {},
            "source": "open-meteo",
        }
    except (requests.RequestException, ValueError, IndexError) as e:
        log(f"open-meteo forecast error: {e}")
        return None


def has_rain(data: dict, is_day_summary: bool) -> bool:
    if is_day_summary:
        prec = data.get("precipitation", {})
        total = prec.get("total", 0) if isinstance(prec, dict) else 0
        return float(total or 0) > 0
    # hourly-style: rain.1h or weather main/id
    if "rain" in data and data["rain"]:
        return True
    weather = data.get("weather", [{}])
    if weather:
        main = weather[0].get("main", "").lower()
        wid = weather[0].get("id", 0)
        if main in ("rain", "drizzle") or 500 <= wid < 600:
            return True
    return False


def format_yesterday(data: dict, city: str) -> str:
    """Format yesterday's weather from day_summary response."""
    temp = data.get("temperature", {})
    if not isinstance(temp, dict):
        temp = {}
    tmin = temp.get("min")
    tmax = temp.get("max")
    if tmin is None and tmax is None:
        return f"  📅 Dün: Veri alınamadı"

    tmin = round(float(tmin)) if tmin is not None else "?"
    tmax = round(float(tmax)) if tmax is not None else "?"
    desc = "Yağışlı" if has_rain(data, True) else "Günlük veriler"

    parts = [f"  📅 Dün: {tmin}°C - {tmax}°C, {desc}"]
    if has_rain(data, True):
        parts.append(" ☔")
    if isinstance(tmin, (int, float)) and tmin < 5:
        parts.append(" ❄")
    if isinstance(tmax, (int, float)) and tmax > 30:
        parts.append(" 🔥")
    return "".join(parts)


def format_tomorrow(data: dict, city: str) -> str:
    """Format tomorrow's forecast from onecall daily[1]."""
    temp = data.get("temp", {})
    if not isinstance(temp, dict):
        temp = {}
    tmin = temp.get("min")
    tmax = temp.get("max")
    weather = data.get("weather", [{}])
    desc = weather[0].get("description", "—") if weather else "—"

    if tmin is None and tmax is None:
        return f"  📆 Yarın: Veri alınamadı"

    tmin = round(float(tmin)) if tmin is not None else "?"
    tmax = round(float(tmax)) if tmax is not None else "?"
    line = f"  📆 Yarın: {tmin}°C - {tmax}°C, {desc}"

    warnings = []
    if has_rain(data, False):
        warnings.append(" ☔")
    if isinstance(tmin, (int, float)) and tmin < 5:
        warnings.append(" ❄")
    if isinstance(tmax, (int, float)) and tmax > 30:
        warnings.append(" 🔥")
    return line + "".join(warnings)


def build_message(api_key: str, yesterday: str) -> str:
    """Build the full Telegram message for all cities."""
    lines = [
        "🌤️ *Hava Durumu Özeti*",
        f"_Tarih: {yesterday} (dün) / yarın_",
        "",
    ]

    for name, lat, lon in CITIES:
        lines.append(f"*{name}*")
        yes_data = fetch_yesterday_weather(lat, lon, api_key, yesterday)
        if not yes_data:
            log(f"Falling back to Open-Meteo archive for yesterday ({name})")
            yes_data = fetch_open_meteo_yesterday(lat, lon, yesterday)
        if yes_data:
            lines.append(format_yesterday(yes_data, name))
        else:
            lines.append("  📅 Dün: Veri alınamadı")

        tom_data = fetch_tomorrow_forecast(lat, lon, api_key)
        if not tom_data:
            log(f"Falling back to Open-Meteo forecast for tomorrow ({name})")
            tom_data = fetch_open_meteo_tomorrow(lat, lon)
        if tom_data:
            lines.append(format_tomorrow(tom_data, name))
        else:
            lines.append("  📆 Yarın: Veri alınamadı")
        lines.append("")

    return "\n".join(lines).strip()


def send_telegram(token: str, chat_id: str, text: str) -> bool:
    """Send message via Telegram Bot API."""
    try:
        bot = Bot(token=token)
        bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
        )
        log("Telegram message sent successfully")
        return True
    except Exception as e:
        log(f"Telegram send error: {e}")
        return False


def main() -> None:
    log("Weather bot starting")

    api_key = os.environ.get("WEATHER_API_KEY")
    token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("CHAT_ID")

    if not all((api_key, token, chat_id)):
        log("Missing env: WEATHER_API_KEY, BOT_TOKEN, CHAT_ID")
        sys.exit(1)

    yesterday = get_yesterday_date_turkey()
    log(f"Fetching weather for yesterday={yesterday} and tomorrow")

    msg = build_message(api_key, yesterday)
    if not msg:
        log("Message empty, aborting")
        sys.exit(1)

    if not send_telegram(token, chat_id, msg):
        sys.exit(1)

    log("Weather bot finished successfully")


if __name__ == "__main__":
    main()
