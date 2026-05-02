# ZargoBot — WhatsApp oziq-ovqat yetkazib berish boti

Зарзамин қишлоғи учун автоматик WhatsApp бот. Мижозлар билан AI ёрдамида сухбат қилади, буюртма йиғади ва админга юборади.

## Имкониятлари

- 🤖 OpenAI GPT-4o-mini орқали табиий сухбат
- 🛒 Google Sheets'дан маҳсулот ва нархларни автоматик олиш
- 👥 Мижозлар базаси (исм, телефон, тарих)
- 📊 Ҳафталик ва ойлик автоматик ҳисоботлар
- ⏰ Тунги буюртмалар (эртасига тасдиқлаш)
- 🔄 Автоматик эслатмалар (re-order, нонушта, sog'индик)
- 🎁 Содиқлик дастури (ҳар 10-буюртмага сов'ға)
- 👑 Админ буйруқлари (ҳисобот, бугун, мижоз, стоп/старт)

## Лойиҳа тузилиши

```
ZargoBotWhatsApp/
├── main.py          ← Flask сервер (webhook, cron)
├── config.py        ← Созлама ва константалар
├── sheets.py        ← Google Sheets API (Apps Script орқали)
├── ai.py            ← OpenAI GPT интеграция
├── whatsapp.py      ← Green API (WhatsApp)
├── handlers.py      ← Мижоз хабар ишловчиси
├── admin.py         ← Админ буйруқлари
├── reminders.py     ← Cron task'лар (эслатмалар)
├── reports.py       ← Ҳисобот генерация
├── prompts.py       ← AI учун system prompt'лар
├── apps_script.gs   ← Google Apps Script коди
├── requirements.txt
├── Procfile
├── .gitignore
├── .env.example
└── README.md
```

## Созлаш

### 1. Google Sheet

4 та варақ бор Sheet ярат: `Маҳсулотлар`, `Мижозлар Малумотлари`, `Буюртмалар`, `Тунги_буюртмалар`.

`apps_script.gs` файлини Sheet'нинг Apps Script муҳарририга солиб, Web app сифатида deploy қил.

### 2. Atrof-muhit o'zgaruvchilari (Render Dashboard)

```
OPENAI_API_KEY=sk-...
GREEN_API_INSTANCE_ID=7107601809
GREEN_API_TOKEN=...
SHEETS_URL=https://script.google.com/macros/s/.../exec
CRON_SECRET=zargo-bot-cron-2026
```

### 3. Render'га deploy

GitHub репога push қил, Render'да янги Web Service яратиб шу репога улаб қўй.

### 4. Webhook'ни созлаш

Бир мартагина:

```
https://your-bot.onrender.com/setup-webhook?secret=YOUR_CRON_SECRET
```

### 5. Cron task'ларни созлаш

[cron-job.org](https://cron-job.org) бепул хизматидан фойдаланиб қуйидагиларни сози:

| Endpoint | Жадвал | Мақсад |
|----------|--------|--------|
| `/cron/morning-night-orders` | Ҳар куни 08:00 | Тунги буюртма эслатма |
| `/cron/breakfast-reminder` | Ҳар куни 20:00 | Нонушта эслатма |
| `/cron/reorder-reminder` | Ҳар куни 15:00 | Re-order эслатма |
| `/cron/loyalty-recovery` | Ҳар куни 12:00 | "Sog'индик" эслатма |
| `/cron/weekly-report` | Ҳар душанба 08:00 | Ҳафталик ҳисобот |
| `/cron/monthly-report` | Ҳар ой 1-сана 08:00 | Ойлик ҳисобот |
| `/cron/keep-alive` | Ҳар 10 дақиқада | Render uxlamasligi учун |

Ҳаммаси `?secret=YOUR_CRON_SECRET` қўш.

## Админ буйруқлари

Админ WhatsApp орқали ботга шу буйруқларни юбориши мумкин:

| Буйруқ | Тавсифи |
|--------|---------|
| `ҳисобот` | Ойлик ҳисобот |
| `ҳафталик` | Ҳафталик ҳисобот |
| `бугун` | Бугунги буюртмалар |
| `мижоз +992XXX` | Мижоз тарихи |
| `стоп` | Ботни вақтинча тўхтатиш |
| `старт` | Қайта ишга тушириш |
| `ёрдам` | Барча буйруқлар |

## Ҳолатни текшириш

```
https://your-bot.onrender.com/health
```

Бу ҳамма хизматлар ишлаётганини JSON форматда қайтаради.
