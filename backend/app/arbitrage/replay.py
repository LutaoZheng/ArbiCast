def replay_snapshots(snapshots:list[dict],latencies_ms=(0,100,250,500,1000))->list[dict]:
    """Uses observed snapshots only; never interpolates unavailable precision."""
    if not snapshots:return [{"latency_ms":x,"samples":0,"executable_rate":None,"average_edge":None,"estimated_pnl":None,"precision":"insufficient_data"} for x in latencies_ms]
    origin=snapshots[0]["timestamp"]
    rows=[]
    for latency in latencies_ms:
        eligible=[s for s in snapshots if (s["timestamp"]-origin).total_seconds()*1000>=latency]
        if not eligible:rows.append({"latency_ms":latency,"samples":0,"executable_rate":None,"average_edge":None,"estimated_pnl":None,"precision":"insufficient_data"});continue
        sample=eligible[0];edge=sample["net_edge"];rows.append({"latency_ms":latency,"samples":1,"executable_rate":float(edge>0),"average_edge":edge,"estimated_pnl":edge*sample["available_liquidity"],"precision":"observed_snapshot"})
    return rows
