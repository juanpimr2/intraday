import os,csv,random,datetime as dt
os.makedirs("./data/csv", exist_ok=True)
assets={"GOLD":1900.0,"TSLA":180.0,"DE40":16000.0,"SP35":9800.0}
start=dt.datetime(2025,4,1); end=dt.datetime(2025,10,1)
times=[dt.time(8,0),dt.time(12,0),dt.time(15,30),dt.time(19,0)]
random.seed(7)
for epic,base in assets.items():
    p=base; path=os.path.join("data","csv",f"{epic}.csv")
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["snapshotTime","openPrice","highPrice","lowPrice","closePrice","volume"])
        d=start
        while d<=end:
            for t in times:
                m=d.month
                drift=(0.15 if m in (4,5,6) else (-0.1 if m==9 else 0.02))
                noise=random.uniform(-0.08,0.08)
                o=p; p=max(0.1, p*(1+(drift+noise)/100.0)); c=p
                h=max(o,c)*(1+random.uniform(0.0005,0.003))
                l=min(o,c)*(1-random.uniform(0.0005,0.003))
                ts=dt.datetime.combine(d,t).isoformat()+"Z"
                w.writerow([ts,round(o,4),round(h,4),round(l,4),round(c,4),random.randint(1000,5000)])
            d+=dt.timedelta(days=1)
print("OK: CSVs en .\\data\\csv")
