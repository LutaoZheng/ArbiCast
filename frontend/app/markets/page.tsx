import { PageHeader } from "@/components/UI";
import { MarketsLive } from "@/components/MarketsLive";
import { api } from "@/lib/api";
import type { Market } from "@/lib/types";
export default async function Markets(){const markets=await api<Market[]>('/markets');return <><PageHeader eyebrow="LIVE MARKET DATA" title="市场" english="Markets" description="查看两个平台的实时价格。关注的市场会持续刷新盘口。\nBrowse live prices across both platforms. Watched markets refresh automatically."/><MarketsLive initial={markets}/></>}
