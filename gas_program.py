import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from matplotlib.dates import DateFormatter, YearLocator
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import warnings

warnings.filterwarnings("ignore")

api_key = "rUUb0ZAuhhPgDz1LMybZptft3h8H6CjHPV4ToCN1"

url = (
    "https://api.eia.gov/v2/petroleum/pri/refmg2/data/"
    f"?api_key={api_key}"
    "&frequency=monthly"
    "&data[]=value"
    "&start=1994-01"
    f"&end={datetime.now().strftime('%Y-%m')}"
    "&sort[0][column]=period"
    "&sort[0][direction]=asc"
    "&facets[duoarea][]=NUS"
    "&facets[product][]=EPMRU"
    "&facets[process][]=PTG"
    "&offset=0"
    "&length=5000"
)

response = requests.get(url)
if response.status_code != 200:
    print("Помилка API:", response.status_code, response.text)
    exit()

data = response.json()
df = pd.DataFrame(data["response"]["data"])

df = df[df["value"].notna()].copy()
df["value"] = pd.to_numeric(df["value"])
df["period"] = pd.to_datetime(df["period"])
df = df.sort_values("period").set_index("period")

model = ExponentialSmoothing(
    df["value"],
    trend="add",
    seasonal="add",
    seasonal_periods=12
).fit()

forecast_steps = 36
forecast = model.forecast(forecast_steps)

future_dates = pd.date_range(
    start=df.index[-1] + pd.offsets.MonthBegin(1),
    periods=forecast_steps,
    freq="MS"
)

plt.style.use("seaborn-v0_8-darkgrid")
fig, ax = plt.subplots(figsize=(16, 8))

ax.plot(
    df.index,
    df["value"],
    color="#e74c3c",
    linewidth=2.5,
    marker="o",
    markersize=5,
    label="Історичні ціни"
)

ax.plot(
    future_dates,
    forecast,
    color="darkred",
    linestyle="--",
    linewidth=3,
    marker="o",
    markersize=7,
    label=f"Прогноз на {forecast_steps} місяців"
)

first_date = df.index[0]
first_price = df["value"].iloc[0]
ax.annotate(
    f'{first_price:.2f}\nПочаток',
    xy=(first_date, first_price),
    xytext=(90, 70),
    textcoords="offset points",
    fontsize=10,
    fontweight='bold',
    color="#2c3e50",
    ha='left',
    va='bottom',
    bbox=dict(boxstyle="round,pad=0.5", fc="yellow", ec="orange", alpha=0.85, lw=1.2),
    arrowprops=dict(arrowstyle="->", color="orange", lw=1.5),
    clip_on=False
)

last_hist_date = df.index[-1]
last_hist_price = df["value"].iloc[-1]
ax.annotate(
    f'{last_hist_price:.2f}\nОстання реальна',
    xy=(last_hist_date, last_hist_price),
    xytext=(-80, -35),
    textcoords="offset points",
    fontsize=9,
    fontweight='bold',
    color="#27ae60",
    ha='right',
    va='top',
    bbox=dict(boxstyle="round,pad=0.5", fc="#d4edda", ec="#27ae60", alpha=0.9),
    arrowprops=dict(arrowstyle="->", color="#27ae60", lw=1.3),
    clip_on=False
)

first_forecast_date = future_dates[0]
first_forecast_price = forecast[0]
ax.annotate(
    f'{first_forecast_price:.2f}\nПочаток прогнозу',
    xy=(first_forecast_date, first_forecast_price),
    xytext=(-30, 55),
    textcoords="offset points",
    fontsize=10,
    fontweight='bold',
    color="#c0392b",
    ha='right',
    va='bottom',
    bbox=dict(boxstyle="round,pad=0.5", fc="#ffebee", ec="#c0392b", alpha=0.9),
    arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.3),
    clip_on=False
)

last_forecast_date = future_dates[-1]
last_forecast_price = forecast[-1]
ax.annotate(
    f'{last_forecast_price:.2f}\nКінець прогнозу',
    xy=(last_forecast_date, last_forecast_price),
    xytext=(0, 50),
    textcoords="offset points",
    fontsize=11,
    fontweight='bold',
    color="#8e44ad",
    ha='center',
    va='bottom',
    bbox=dict(boxstyle="round,pad=0.6", fc="#f5eef8", ec="#8e44ad", alpha=0.9),
    arrowprops=dict(arrowstyle="->", color="#8e44ad", lw=1.5),
    clip_on=False
)

ax.set_title("Динаміка цін на бензин США + прогноз\n(з ключовими позначками)", fontsize=16, fontweight="bold")
ax.set_xlabel("Рік", fontsize=12)
ax.set_ylabel("Ціна, $/галон", fontsize=12)

ax.xaxis.set_major_locator(YearLocator())
ax.xaxis.set_major_formatter(DateFormatter("%Y"))
plt.xticks(rotation=0)

ax.legend(fontsize=11, loc="upper left")
ax.grid(True, alpha=0.6)
ax.margins(y=0.18)

plt.tight_layout()
plt.show()