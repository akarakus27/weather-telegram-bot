"""
Telegram Weather Bot - Daily weather report for Gebze and Istanbul.
Sends yesterday's summary and tomorrow's forecast at 20:00 Turkey time.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Any

import requests
from telegram import Bot

# OpenWeather One Call API 3.0 base URLs
ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"
DAY_SUMMARY_URL = "https://api.openweathermap.org/data/3.0/onecall/day_summary"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

# Cities: (name, lat, lon)
CITIES = [
    ("Gebze", 40.8028, 29.4307),
    ("İstanbul", 41.0082, 28.9784),
]

# Turkey timezone offset (UTC+3)
TZ_TURKEY = "+03:00"
MONTHS_TR = [
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
]


def log(msg: str) -> None:
    print(msg, flush=True)


def get_yesterday_date_turkey() -> str:
    """Return yesterday's date in YYYY-MM-DD (Turkey time)."""
    # Use UTC+3 for Turkey
    now = datetime.utcnow() + timedelta(hours=3)
    yesterday = now - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def now_turkey() -> datetime:
    """Return current datetime in Turkey timezone (UTC+3)."""
    return datetime.utcnow() + timedelta(hours=3)


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


def fetch_today_tomorrow_forecast(lat: float, lon: float, api_key: str) -> tuple[dict | None, dict | None]:
    """Fetch both today's and tomorrow's daily forecast via onecall."""
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
            log("onecall: insufficient daily forecast for today/tomorrow")
            return None, None
        return daily[0], daily[1]
    except requests.HTTPError as e:
        body = (e.response.text or "")[:300] if e.response is not None else ""
        log(f"onecall(today/tomorrow) HTTP error: {e}; response={body}")
        return None, None
    except requests.RequestException as e:
        log(f"onecall(today/tomorrow) API error: {e}")
        return None, None
    except (ValueError, KeyError) as e:
        log(f"onecall(today/tomorrow) parse error: {e}")
        return None, None


def _safe_get_daily_value(daily: dict[str, Any], key: str, index: int) -> Any:
    """Return daily[key][index] safely."""
    values = daily.get(key)
    if not isinstance(values, list) or len(values) <= index:
        return None
    return values[index]


def _map_open_meteo_code(code: Any) -> str:
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
    return weather_map.get(code, "—")


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
        tmin = _safe_get_daily_value(daily, "temperature_2m_min", 0)
        tmax = _safe_get_daily_value(daily, "temperature_2m_max", 0)
        precip = _safe_get_daily_value(daily, "precipitation_sum", 0) or 0
        if tmin is None and tmax is None:
            return None
        return {
            "temperature": {"min": tmin, "max": tmax},
            "precipitation": {"total": precip},
            "source": "open-meteo-archive",
        }
    except (requests.RequestException, ValueError, IndexError) as e:
        log(f"open-meteo archive error: {e}")
        return None


def fetch_open_meteo_yesterday_from_forecast(lat: float, lon: float) -> dict | None:
    """Second fallback: get yesterday from Open-Meteo forecast API using past_days."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum",
        "past_days": 1,
        "forecast_days": 1,
        "timezone": "Europe/Istanbul",
    }
    try:
        r = requests.get(OPEN_METEO_FORECAST_URL, params=params, timeout=15)
        r.raise_for_status()
        payload = r.json()
        daily = payload.get("daily", {})
        if not isinstance(daily, dict):
            return None
        tmin = _safe_get_daily_value(daily, "temperature_2m_min", 0)
        tmax = _safe_get_daily_value(daily, "temperature_2m_max", 0)
        precip = _safe_get_daily_value(daily, "precipitation_sum", 0) or 0
        if tmin is None and tmax is None:
            return None
        return {
            "temperature": {"min": tmin, "max": tmax},
            "precipitation": {"total": precip},
            "source": "open-meteo-forecast-past",
        }
    except (requests.RequestException, ValueError, IndexError) as e:
        log(f"open-meteo yesterday-from-forecast error: {e}")
        return None


def fetch_open_meteo_tomorrow(lat: float, lon: float) -> dict | None:
    """Fallback: fetch tomorrow forecast from Open-Meteo forecast API."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_min,temperature_2m_max,weather_code,precipitation_sum",
        "forecast_days": 2,
        "timezone": "Europe/Istanbul",
    }
    try:
        r = requests.get(OPEN_METEO_FORECAST_URL, params=params, timeout=15)
        r.raise_for_status()
        payload = r.json()
        daily = payload.get("daily", {})
        if not isinstance(daily, dict):
            return None
        tmin = _safe_get_daily_value(daily, "temperature_2m_min", 1)
        tmax = _safe_get_daily_value(daily, "temperature_2m_max", 1)
        code = _safe_get_daily_value(daily, "weather_code", 1)
        if code is None:
            code = _safe_get_daily_value(daily, "weathercode", 1)
        precip = _safe_get_daily_value(daily, "precipitation_sum", 1) or 0
        if tmin is None and tmax is None:
            return None
        return {
            "temp": {"min": tmin, "max": tmax},
            "weather": [{"description": _map_open_meteo_code(code), "id": 500 if precip > 0 else 800}],
            "rain": {"1h": precip} if precip > 0 else {},
            "source": "open-meteo-forecast",
        }
    except (requests.RequestException, ValueError, IndexError) as e:
        log(f"open-meteo forecast error: {e}")
        return None


def fetch_openweather_tomorrow_5day(lat: float, lon: float, api_key: str) -> dict | None:
    """Second fallback: use free OpenWeather 5-day/3-hour endpoint for tomorrow."""
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",
        "lang": "tr",
    }
    try:
        r = requests.get(OPENWEATHER_FORECAST_URL, params=params, timeout=15)
        r.raise_for_status()
        payload = r.json()
        entries = payload.get("list", [])
        if not isinstance(entries, list) or not entries:
            return None

        now_tr = datetime.utcnow() + timedelta(hours=3)
        tomorrow_date = (now_tr + timedelta(days=1)).date()
        tomorrow_entries = []
        for item in entries:
            dt_txt = item.get("dt_txt")
            if not dt_txt:
                continue
            try:
                dt = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if dt.date() == tomorrow_date:
                tomorrow_entries.append(item)

        if not tomorrow_entries:
            return None

        min_temp = min((entry.get("main", {}).get("temp_min") for entry in tomorrow_entries if isinstance(entry.get("main"), dict)), default=None)
        max_temp = max((entry.get("main", {}).get("temp_max") for entry in tomorrow_entries if isinstance(entry.get("main"), dict)), default=None)
        weather_desc = "—"
        weather_id = 800
        for entry in tomorrow_entries:
            weather = entry.get("weather", [])
            if weather and isinstance(weather, list):
                weather_desc = weather[0].get("description", "—")
                weather_id = weather[0].get("id", 800)
                break

        if min_temp is None and max_temp is None:
            return None

        rain_total = 0.0
        for entry in tomorrow_entries:
            rain = entry.get("rain", {})
            if isinstance(rain, dict):
                rain_total += float(rain.get("3h") or 0)

        return {
            "temp": {"min": min_temp, "max": max_temp},
            "weather": [{"description": weather_desc, "id": weather_id}],
            "rain": {"1h": rain_total} if rain_total > 0 else {},
            "source": "openweather-5day",
        }
    except (requests.RequestException, ValueError, TypeError) as e:
        log(f"openweather 5-day forecast fallback error: {e}")
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


def _weather_emoji(weather_id: int, has_precipitation: bool) -> str:
    if has_precipitation or 500 <= weather_id < 700:
        return "🌧"
    if 200 <= weather_id < 300:
        return "⛈"
    if 800 == weather_id:
        return "🌤"
    if weather_id in (801, 802):
        return "🌥"
    if weather_id in (803, 804):
        return "☁"
    return "🌤"


def _format_temp_range(data: dict, key: str) -> tuple[str, str]:
    temp = data.get(key, {})
    if not isinstance(temp, dict):
        temp = {}
    tmin = temp.get("min")
    tmax = temp.get("max")
    tmin_str = f"{round(float(tmin))}°" if tmin is not None else "?°"
    tmax_str = f"{round(float(tmax))}°" if tmax is not None else "?°"
    return tmin_str, tmax_str


def _capitalize_tr(text: str) -> str:
    if not text:
        return "—"
    return text[0].upper() + text[1:]


def format_yesterday_line(data: dict) -> str:
    tmin, tmax = _format_temp_range(data, "temperature")
    is_rainy = has_rain(data, True)
    desc = "Hafif yağmur" if is_rainy else "Parçalı bulutlu"
    emoji = "🌧" if is_rainy else "🌥"
    return f"Dün: {tmin}–{tmax} {emoji} {desc}"


def format_daily_line(label: str, data: dict) -> str:
    tmin, tmax = _format_temp_range(data, "temp")
    weather = data.get("weather", [{}])
    first = weather[0] if weather else {}
    desc = _capitalize_tr(first.get("description", "—"))
    wid = int(first.get("id", 800) or 800)
    is_rainy = has_rain(data, False)
    emoji = _weather_emoji(wid, is_rainy)
    return f"{label}: {tmin}–{tmax} {emoji} {desc}"


def format_warning(today: dict, tomorrow: dict) -> str | None:
    today_temp = today.get("temp", {}) if isinstance(today.get("temp", {}), dict) else {}
    tomorrow_temp = tomorrow.get("temp", {}) if isinstance(tomorrow.get("temp", {}), dict) else {}
    today_max = today_temp.get("max")
    tomorrow_max = tomorrow_temp.get("max")
    if today_max is None or tomorrow_max is None:
        return None

    diff = round(float(today_max) - float(tomorrow_max))
    if diff <= 0:
        return None

    rainy_tomorrow = has_rain(tomorrow, False)
    pop = tomorrow.get("pop")
    pop_text = f" (%{round(float(pop) * 100)})" if pop is not None else ""
    note = "şemsiyeni almayı unutma ☔" if rainy_tomorrow else "biraz kalın giyin 💕"
    return f"⚠ Yarın {diff}° daha soğuk, {note}{pop_text}"


def format_report_header() -> list[str]:
    now = now_turkey()
    month_name = MONTHS_TR[now.month - 1]
    return [
        f"🕒 {now.day} {month_name} {now.year} – {now.strftime('%H:%M')}",
        "🌤 Nur’cuğum için Hava Durumu 💛",
        "",
    ]


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
    lines = format_report_header()

    for name, lat, lon in CITIES:
        lines.append(f"📍 {name}")
        yes_data = fetch_yesterday_weather(lat, lon, api_key, yesterday)
        if not yes_data:
            log(f"Falling back to Open-Meteo archive for yesterday ({name})")
            yes_data = fetch_open_meteo_yesterday(lat, lon, yesterday)
        if not yes_data:
            log(f"Falling back to Open-Meteo forecast(past_days) for yesterday ({name})")
            yes_data = fetch_open_meteo_yesterday_from_forecast(lat, lon)
        if yes_data:
            lines.append(format_yesterday_line(yes_data))
        else:
            lines.append("Dün: Veri alınamadı")

        today_data, tom_data = fetch_today_tomorrow_forecast(lat, lon, api_key)
        if today_data:
            lines.append(format_daily_line("Bugün", today_data))
        else:
            lines.append("Bugün: Veri alınamadı")

        if not tom_data:
            log(f"Falling back to Open-Meteo forecast for tomorrow ({name})")
            tom_data = fetch_open_meteo_tomorrow(lat, lon)
        if not tom_data:
            log(f"Falling back to OpenWeather 5-day forecast for tomorrow ({name})")
            tom_data = fetch_openweather_tomorrow_5day(lat, lon, api_key)
        if tom_data:
            lines.append(format_daily_line("Yarın", tom_data))
            if today_data:
                warning = format_warning(today_data, tom_data)
                if warning:
                    lines.append(warning)
        else:
            lines.append("Yarın: Veri alınamadı")
        lines.append("")

    lines.append("✨ Dikkatli git gel güzelim 💛")
    return "\n".join(lines).strip()


def send_telegram(token: str, chat_id: str, text: str) -> bool:
    """Send message via Telegram Bot API."""
    try:
        bot = Bot(token=token)
        bot.send_message(
            chat_id=chat_id,
            text=text,
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
