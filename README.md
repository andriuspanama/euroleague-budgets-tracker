# EuroLeague Budgets Tracker 2026/27

Renka krepšinio klubų biudžetų informaciją (Graikija, Ispanija, Vokietija, Italija, Turkija) iš straipsnių ir X/Twitter žurnalistų bei insiderių.

### Pagrindiniai klubai
- **Graikija**: Panathinaikos, Olympiacos
- **Ispanija**: Real Madrid, Barcelona, Valencia, Baskonia
- **Vokietija**: Bayern Munich
- **Italija**: Olimpia Milano, Virtus Bologna
- **Turkija**: Fenerbahce, Anadolu Efes, Beşiktaş

### Kaip paleisti

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Įrašyk savo X Bearer Token į .env

python main.py
```

### Komandos
```bash
python main.py                # viskas
python main.py --web          # tik straipsniai
python main.py --x            # tik X (paieška + insideriai)
```

Rezultatai saugomi į `data/` aplanką (CSV + JSON).

### X API
1. https://developer.x.com/ → Create Project + App
2. Nukopijuok **Bearer Token**
3. Įrašyk į `.env` failą

### Pridėti daugiau žurnalistų
Atidaryk `main.py` ir redaguok sąrašą `X_INSIDERS`.
