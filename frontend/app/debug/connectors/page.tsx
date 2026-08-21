import { PageHeader } from "@/components/UI";
import { ConnectorDebug } from "@/components/ConnectorDebug";
import { api } from "@/lib/api";
import type { Health, Market } from "@/lib/types";
type Diagnostics=Health&{recent_requests:{platform:string;method:string;path:string;status:number|null;latency_ms:number;timestamp:string;error:string|null}[]};
export default async function DebugConnectors(){const [diagnostics,markets]=await Promise.all([api<Diagnostics>('/connectors'),api<Market[]>('/markets')]);return <><PageHeader eyebrow="DEVELOPER ONLY" title="开发调试" english="Connector Debug" description="用于验证连接器、原始响应与标准化盘口。普通研究流程不需要进入此页面。"/><ConnectorDebug initial={diagnostics} markets={markets}/></>}
