import "./globals.css";
import { Nav } from "@/components/Nav";
export const dynamic = "force-dynamic";
export const metadata={title:"ArbiCast — Cross-Market Research",description:"Kalshi × Polymarket arbitrage research"};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="zh-CN"><body><Nav/><main className="min-h-screen px-5 py-8 md:ml-[230px] md:px-10 md:py-10 lg:px-14"><div className="mx-auto max-w-[1320px]">{children}</div></main></body></html>}
