# 🌤️ Telegram Hava Durumu Botu

Her gün saat 20:00’da (Türkiye saati, UTC+3) otomatik olarak Telegram’a hava durumu özeti gönderen bot. Gebze ve İstanbul için dünün hava durumu ile yarının tahminini içerir.

## Özellikler

- **Dünün havası**: Min/max sıcaklık, yağış
- **Yarının tahmini**: Min/max sıcaklık, hava açıklaması
- **Uyarılar**: Yağmur (☔), soğuk (<5°C ❄), sıcak (>30°C 🔥)
- OpenWeather yanıt vermezse Open-Meteo ile otomatik yedek veri
- GitHub Actions ile zamanlanmış çalıştırma (günlük 20:00 TR)
- Manuel tetikleme desteği

## Kurulum

### 1. Repoyu klonlayın

```bash
git clone https://github.com/KULLANICI_ADI/weather-telegram-bot.git
cd weather-telegram-bot
```

### 2. Gerekli anahtarları hazırlayın

#### OpenWeather API Key

1. [OpenWeather](https://openweathermap.org/) hesabı oluşturun
2. [One Call API 3.0](https://openweathermap.org/api/one-call-3) aboneliğini açın (günlük 1000 ücretsiz çağrı)
3. [API Keys](https://home.openweathermap.org/api_keys) sayfasından anahtarınızı alın

#### Telegram Bot Token

1. Telegram’da [@BotFather](https://t.me/BotFather) ile yazışın
2. `/newbot` komutuyla yeni bot oluşturun
3. Size verilen token’ı kaydedin

#### Chat ID

1. Oluşturduğunuz botu kullanacağınız sohbete (grup/kanal/özel) ekleyin
2. Sohbete en az bir mesaj gönderin
3. Chat ID’yi almak için:
   - [@userinfobot](https://t.me/userinfobot) ile yazışın (özel mesaj için), **veya**
   - Tarayıcıda şu adresi açın: `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates` — gelen JSON içinde `chat.id` değerini bulun

### 3. GitHub’a push edin

```bash
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/KULLANICI_ADI/weather-telegram-bot.git
git branch -M main
git push -u origin main
```

### 4. GitHub Secrets tanımlayın

1. Repo sayfasında **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** ile şu secret’ları ekleyin:

| Secret Adı        | Değer                     |
|-------------------|---------------------------|
| `BOT_TOKEN`       | Telegram bot token        |
| `WEATHER_API_KEY` | OpenWeather API key       |
| `CHAT_ID`         | Hedef chat/kanal ID       |

### 5. Actions’ı etkinleştirin

1. **Actions** sekmesine gidin
2. İlk kez ise “I understand my workflows, go ahead and enable them” ile etkinleştirin

## Kullanım

### Otomatik çalıştırma

Her gün **17:00 UTC** (Türkiye saatiyle **20:00**) otomatik çalışır.

### Manuel çalıştırma

1. **Actions** → **Daily Weather Report**
2. **Run workflow** → **Run workflow**

## Yerel çalıştırma

```bash
pip install -r requirements.txt
```

Ortam değişkenlerini ayarlayın ve çalıştırın:

```bash
export BOT_TOKEN="your-telegram-bot-token"
export WEATHER_API_KEY="your-openweather-api-key"
export CHAT_ID="your-chat-id"
python main.py
```

Windows (PowerShell):

```powershell
$env:BOT_TOKEN="your-telegram-bot-token"
$env:WEATHER_API_KEY="your-openweather-api-key"
$env:CHAT_ID="your-chat-id"
python main.py
```

## Teknolojiler

- Python 3.11
- OpenWeather One Call API 3.0
- python-telegram-bot 13.15
- GitHub Actions

## Lisans

MIT
