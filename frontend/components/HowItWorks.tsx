"use client";
import { useState } from "react";
import { CircleHelp, X } from "lucide-react";
const steps=[
  ["获取实时数据","Fetch live market data","从 Kalshi 和 Polymarket 获取市场与盘口。"],
  ["寻找相同事件","Find the same event","比较两个平台上可能对应的市场。"],
  ["确认结算规则","Verify resolution rules","只有真正等价的合约才能继续。"],
  ["比较真实盘口","Compare order books","检查 YES / NO 价格与可成交数量。"],
  ["扣除执行成本","Subtract execution costs","计入手续费、滑点和安全缓冲。"],
  ["显示可执行机会","Show executable opportunities","扣除成本后仍有正收益才会显示。"],
];
export function HowItWorks(){const [open,setOpen]=useState(false);return <><button onClick={()=>setOpen(true)} className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-left text-sm font-semibold text-zinc-600 shadow-sm"><CircleHelp size={16}/><span>如何使用<span className="ml-1 text-xs font-normal text-zinc-400">How it works</span></span></button>{open&&<div className="fixed inset-0 z-40 grid place-items-center bg-black/15 p-5 backdrop-blur-sm" onClick={()=>setOpen(false)}><div className="card max-h-[90vh] w-full max-w-xl overflow-auto p-7" onClick={e=>e.stopPropagation()}><div className="flex items-start justify-between"><div><h2 className="m-0 text-2xl font-semibold">ArbiCast 如何工作？</h2><div className="mt-1 text-xs uppercase tracking-wider text-zinc-400">How it works</div></div><button onClick={()=>setOpen(false)} className="rounded-xl bg-zinc-100 p-2"><X size={17}/></button></div><div className="mt-7 space-y-5">{steps.map(([zh,en,detail],i)=><div key={zh} className="flex gap-4"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-black text-xs font-semibold text-white">{i+1}</span><div><div className="font-semibold">{zh}</div><div className="text-[11px] uppercase tracking-wider text-zinc-400">{en}</div><p className="mb-0 mt-1 text-sm leading-5 text-zinc-500">{detail}</p></div></div>)}</div></div></div>}</>}
