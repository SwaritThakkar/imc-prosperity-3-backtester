import pandas as pd

PRICE_FILES = [
    "/Users/swaritthakkar/Documents/GitHub/imc-prosperity-3-backtester/prosperity3bt/resources/round0/prices_round_0_day_-2.csv",
    "/Users/swaritthakkar/Documents/GitHub/imc-prosperity-3-backtester/prosperity3bt/resources/round0/prices_round_0_day_-1.csv",
]

PRODUCT = "TOMATOES"

OUTPUT = "tomatoes_price_diff.csv"


# =========================
# read csv safely
# =========================

def read_csv(path):

    with open(path, "r") as f:
        first = f.readline()

    sep = ";" if first.count(";") > first.count(",") else ","

    df = pd.read_csv(path, sep=sep)

    df.columns = df.columns.str.lower().str.strip()

    return df


# =========================
# load both days
# =========================

frames = []

for path in PRICE_FILES:

    df = read_csv(path)

    frames.append(df)


df = pd.concat(frames, ignore_index=True)


# =========================
# filter product
# =========================

prod_col = "product" if "product" in df.columns else "symbol"

df = df[df[prod_col] == PRODUCT]


# =========================
# sort by time
# =========================

df = df.sort_values("timestamp").reset_index(drop=True)


# =========================
# ensure numeric
# =========================

df["mid_price"] = pd.to_numeric(df["mid_price"], errors="coerce")


# =========================
# compute diff
# =========================

df["price_diff"] = df["mid_price"].diff()

df["price_diff_pct"] = df["mid_price"].pct_change()


# =========================
# future diff (useful later)
# =========================

df["future_diff"] = df["mid_price"].shift(-1) - df["mid_price"]


# =========================
# save
# =========================

df.to_csv(OUTPUT, index=False)

print("Saved:", OUTPUT)
print("rows:", len(df))