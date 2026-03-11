import pandas as pd
import sqlite3
import requests
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

DB_NAME = "fuel_prices.db"
USD_TO_EUR = 0.92          # приблизний фіксований курс (краще брати історичний, але для простоти)
GALLON_TO_LITER = 3.78541

EXCEL_FILE = "/Users/dmitronevstruev/Downloads/Weekly_Oil_Bulletin_Prices_History_maticni_4web.xlsx"
SHEET_NAME = "Prices with taxes"
GERMANY_COL = 54   # Euro-super 95 Німеччина
DENMARK_COL = 62   # Euro-super 95 Данія

def init_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Видаляємо стару таблицю (тільки якщо хочеш повне очищення)
    cursor.execute("DROP TABLE IF EXISTS prices")
    conn.commit()
    
    # Створюємо таблицю
    cursor.execute('''
    CREATE TABLE prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        country TEXT,
        fuel_type TEXT,
        price REAL,
        currency TEXT,
        source TEXT
    )
    ''')
    conn.commit()
    print("База даних ініціалізована, таблиця prices створена")
    return conn, cursor

def load_usa(cursor, conn):
    api_key = "rUUb0ZAuhhPgDz1LMybZptft3h8H6CjHPV4ToCN1"
    url = (
        "https://api.eia.gov/v2/petroleum/pri/refmg2/data/"
        f"?api_key={api_key}&frequency=monthly&data[]=value"
        "&start=2005-01"
        f"&end={datetime.now().strftime('%Y-%m')}"
        "&sort[0][column]=period&sort[0][direction]=asc"
        "&facets[duoarea][]=NUS&facets[product][]=EPMRU&facets[process][]=PTG"
    )
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        df = pd.DataFrame(data["response"]["data"])
        df = df[df["value"].notna()].copy()
        df["value"] = pd.to_numeric(df["value"])
        df["period"] = pd.to_datetime(df["period"]).dt.strftime("%Y-%m-%d")
        
        added = 0
        for _, row in df.iterrows():
            price_eur_l = (row["value"] / GALLON_TO_LITER) * USD_TO_EUR
            cursor.execute('''
                INSERT OR IGNORE INTO prices (date, country, fuel_type, price, currency, source)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (row["period"], "USA", "Regular Gasoline", round(price_eur_l, 4), "EUR", "EIA API"))
            added += 1
        
        conn.commit()
        print(f"США: додано {added} записів")
    
    except Exception as e:
        print(f"Помилка при завантаженні даних США: {e}")

def load_eu(cursor, conn):
    try:
        df = pd.read_excel(
            EXCEL_FILE,
            sheet_name=SHEET_NAME,
            skiprows=3,
            header=None,
            engine='openpyxl'
        )
        
        df[0] = pd.to_datetime(df[0], errors='coerce')
        df = df.dropna(subset=[0])
        
        for col in [GERMANY_COL, DENMARK_COL]:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(',', '.').str.strip(),
                errors='coerce'
            )
        
        df = df.dropna(subset=[GERMANY_COL, DENMARK_COL])
        
        added = 0
        for _, row in df.iterrows():
            date_str = row[0].strftime('%Y-%m-%d')
            
            # Німеччина
            price_de = row[GERMANY_COL] / 1000
            cursor.execute('''
                INSERT OR IGNORE INTO prices (date, country, fuel_type, price, currency, source)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (date_str, "Germany", "Euro-super 95", round(price_de, 4), "EUR", "EU Oil Bulletin"))
            added += 1
            
            # Данія
            price_dk = row[DENMARK_COL] / 1000
            cursor.execute('''
                INSERT OR IGNORE INTO prices (date, country, fuel_type, price, currency, source)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (date_str, "Denmark", "Euro-super 95", round(price_dk, 4), "EUR", "EU Oil Bulletin"))
            added += 1
        
        conn.commit()
        print(f"Європа (Німеччина + Данія): додано {added} записів")
    
    except FileNotFoundError:
        print(f"Файл Excel не знайдено: {EXCEL_FILE}")
    except Exception as e:
        print(f"Помилка при обробці Excel: {e}")

def analyze_biggest_jump(conn):
    df = pd.read_sql_query("""
        SELECT date, country, price, currency
        FROM prices
        ORDER BY country, date
    """, conn)
    
    if df.empty:
        print("Даних у базі немає")
        return
    
    df['date'] = pd.to_datetime(df['date'])
    df['prev_price'] = df.groupby('country')['price'].shift(1)
    df['jump_percent'] = ((df['price'] - df['prev_price']) / df['prev_price']) * 100
    df = df.dropna(subset=['jump_percent'])
    
    if df.empty:
        print("Немає достатньо даних для розрахунку стрибків")
        return
    
    max_jump = df.loc[df['jump_percent'].idxmax()]
    print("\n" + "="*70)
    print("НАЙБІЛЬШИЙ СТРИБОК:")
    print(f"Країна:     {max_jump['country']}")
    print(f"Дата:       {max_jump['date'].date()}")
    print(f"Стрибок:    +{max_jump['jump_percent']:.1f}%")
    print(f"Ціна:       {max_jump['prev_price']:.4f} → {max_jump['price']:.4f} EUR")
    print("="*70)
    
    print("\nМакс. стрибок по країнах:")
    max_by_country = df.groupby('country')['jump_percent'].max().round(1).sort_values(ascending=False)
    for country, pct in max_by_country.items():
        print(f" {country:10} → +{pct}%")
def plot_prices_with_jump_highlight(conn):
    df = pd.read_sql_query("""
        SELECT date, country, price
        FROM prices
        ORDER BY country, date
    """, conn)
    
    if df.empty:
        print("Немає даних для графіка")
        return
    
    df['date'] = pd.to_datetime(df['date'])
    
    plt.style.use("seaborn-v0_8-darkgrid")
    fig, axes = plt.subplots(3, 1, figsize=(15, 13), sharex=True, sharey=True)
    
    countries = ["USA", "Germany", "Denmark"]
    colors = ["#e74c3c", "#3498db", "#2ecc71"]
    y_min, y_max = 0.2, 2.6  # трохи розширили для Данії
    
    for ax, country, color in zip(axes, countries, colors):
        country_df = df[df['country'] == country].sort_values('date').reset_index(drop=True)
        
        if country_df.empty:
            ax.text(0.5, 0.5, f"Немає даних для {country}", ha='center', va='center', fontsize=12)
            ax.set_title(country)
            continue
        
        # Основна лінія
        ax.plot(country_df['date'], country_df['price'], color=color, linewidth=2.3, marker='o', ms=3.5)
        
        # Обчислення стрибків
        country_df['prev_price'] = country_df['price'].shift(1)
        country_df['jump_pct'] = ((country_df['price'] - country_df['prev_price']) / country_df['prev_price']) * 100
        
        if country_df['jump_pct'].notna().any():
            max_idx = country_df['jump_pct'].idxmax()
            max_row = country_df.loc[max_idx]
            pct = max_row['jump_pct']
            
            start_idx = max_idx - 1 if max_idx > 0 else 0
            start_date = country_df.loc[start_idx, 'date']
            start_price = country_df.loc[start_idx, 'price']
            end_date = max_row['date']
            end_price = max_row['price']
            
            # Друк для дебагу — подивись у консоль!
            print(f"{country}: max jump {pct:.1f}% від {start_price:.4f} → {end_price:.4f} €/л")
            print(f"   Дата: {start_date.date()} → {end_date.date()}")
            
            # Червоний сегмент
            ax.plot([start_date, end_date], [start_price, end_price],
                    color='red', linewidth=6, alpha=0.85, zorder=10)
            
            # Вертикальна лінія на дату стрибка
            ax.axvline(x=end_date, color='red', linestyle='--', alpha=0.4, linewidth=1.5)
            
            # Мітка (з більшим зсувом для високих цін)
            label_y = end_price + 0.18 if end_price > 1.8 else end_price + 0.12
            ax.annotate(f'+{pct:.1f}%\n({end_date.date().strftime("%Y-%m")})',
                        xy=(end_date, end_price),
                        xytext=(end_date, label_y),
                        fontsize=10.5,
                        fontweight='bold',
                        color='darkred',
                        ha='center',
                        va='bottom',
                        bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='red', alpha=0.8),
                        arrowprops=dict(arrowstyle='->', color='darkred', lw=1.5))
        
        ax.set_title(f"{country}", fontsize=14)
        ax.set_ylabel("Ціна €/л", fontsize=11)
        ax.grid(True, alpha=0.5, ls='--')
        ax.set_ylim(y_min, y_max)
    
    axes[-1].set_xlabel("Дата", fontsize=12)
    fig.suptitle("Ціни на бензин (EUR/л) — найбільший стрибок у кожній країні виділений червоним", 
                 fontsize=16, fontweight='bold', y=0.98)
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.show()
# ──────────────────────────────── ЗАПУСК ─────────────────────────────────────
if __name__ == "__main__":
    conn, cursor = init_database()
    
    load_usa(cursor, conn)
    load_eu(cursor, conn)
    
    analyze_biggest_jump(conn)
    plot_prices_with_jump_highlight(conn)
    
    conn.close()
    print("Готово.")