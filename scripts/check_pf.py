import pathlib, pandas as pd

run = sorted(pathlib.Path("reports").glob("run_*"))[-1]
df = pd.read_csv(run / "trades.csv")

def pf_of(frame):
    profits = frame.loc[frame["pnl"] > 0, "pnl"].sum()
    losses  = -frame.loc[frame["pnl"] < 0, "pnl"].sum()
    return float("inf") if losses == 0 else profits / losses, profits, losses

pf, prof, loss = pf_of(df)
print("PF global: {:.2f} | profits={:.2f} | losses={:.2f}".format(pf, prof, loss))

if "regime" in df.columns:
    for k, g in df.groupby("regime"):
        pfk, pk, lk = pf_of(g)
        print("PF {:>9}: {:>6.2f} | profits={:.2f} | losses={:.2f}".format(k, pfk, pk, lk))

if "session" in df.columns:
    for k, g in df.groupby("session"):
        pfk, pk, lk = pf_of(g)
        print("PF sesión {:>7}: {:>6.2f} | profits={:.2f} | losses={:.2f}".format(k, pfk, pk, lk))
