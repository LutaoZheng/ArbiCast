export const terms = {
  overview: ["概览", "Overview"], markets: ["市场", "Markets"], matches: ["匹配", "Matches"],
  opportunities: ["套利机会", "Opportunities"], paper: ["模拟交易", "Paper Trading"], analytics: ["分析", "Analytics"],
  settings: ["设置", "Settings"], debug: ["开发调试", "Developer Debug"], watch: ["关注", "Watch"],
  edge: ["套利空间", "Edge"], netEdge: ["净套利空间", "Net Edge"], orderBook: ["盘口", "Order Book"],
  depth: ["盘口深度", "Order Book Depth"], liquidity: ["流动性", "Liquidity"], vwap: ["成交均价", "VWAP"],
  latency: ["延迟", "Latency"], resolution: ["结算规则", "Resolution Rules"], marketMatching: ["市场匹配", "Market Matching"],
} as const;

export const explanations = {
  bidAsk: "Bid：当前市场愿意买入该结果的最高价格。Ask：当前市场愿意卖出该结果的最低价格。\nBid: highest current buy price. Ask: lowest current sell price.",
  netEdge: "扣除手续费、滑点和安全缓冲后仍然存在的套利空间。\nEdge remaining after fees, slippage and safety buffer.",
  vwap: "按实际盘口深度计算的平均成交价格，不只是最优报价。\nAverage execution price across available order-book levels.",
  liquidity: "在当前盘口中预计可以成交的金额。\nEstimated amount executable at current depth.",
  latency: "请求平台数据所需的时间。\nTime required to receive data from the platform.",
  resolution: "决定合约最终如何判定 YES 或 NO 的规则。\nRules that determine whether the contract resolves YES or NO.",
  orderBook: "市场当前所有买卖报价与可成交数量。\nCurrent buy/sell prices and available quantities.",
} as const;
