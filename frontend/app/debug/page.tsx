import Link from "next/link";
import { PageHeader } from "@/components/UI";
import { CSLDiscoveryPanel } from "@/components/CSLDiscoveryPanel";
import { KalshiSeriesProbe } from "@/components/KalshiSeriesProbe";
const links=[["Markets / 市场","/markets"],["Matches / 匹配","/matches"],["Order Books / 盘口","/markets"],["Research Test / 研究测试","/research-test"],["Connectors & Requests","/debug/connectors"],["Static Opportunities","/opportunities"],["Paper Account","/paper"],["Legacy Performance","/analytics"]];
export default function Debug(){return <><PageHeader eyebrow="ADVANCED" title="调试" english="Debug" description="保留现有市场、匹配、盘口、研究测试与 Connector 能力，但不占据核心研究导航。"/><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{links.map(([name,href])=><Link key={name} href={href} className="card p-6 text-lg font-semibold hover:shadow-md">{name}<div className="mt-2 text-xs font-normal text-zinc-400">Open →</div></Link>)}</div><KalshiSeriesProbe/><CSLDiscoveryPanel/></>}
