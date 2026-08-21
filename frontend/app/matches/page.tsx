import { PageHeader } from "@/components/UI";
import { MatchesReview } from "@/components/MatchesReview";
import { api } from "@/lib/api";
import type { Match } from "@/lib/types";
export default async function Matches(){const matches=await api<Match[]>('/matches');return <><PageHeader eyebrow="CONTRACT EQUIVALENCE" title="市场匹配" english="Market Matching" description="寻找 Kalshi 和 Polymarket 上描述同一个现实事件的合约。\n只有确认结算规则一致后，才会用于套利计算。"/><MatchesReview matches={matches}/></>}
