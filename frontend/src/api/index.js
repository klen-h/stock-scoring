import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 市场行情
export const getMarketOverview = () => http.get('/market/overview')
export const getMarketRealtime = (params) => http.get('/market/realtime', { params })
export const getIndexKline = (symbol, period = 'day') => http.get(`/market/index-kline/${symbol}`, { params: { period } })
export const getRefreshStatus = () => http.get('/market/refresh-status')
export const triggerRefresh = () => http.get('/market/trigger-refresh')

// 个股数据
export const getStockKline = (symbol, params) => http.get(`/stock/kline/${symbol}`, { params })
export const getStockRealtime = (symbol) => http.get(`/stock/realtime/${symbol}`)
export const getStockFundamental = (symbol) => http.get(`/stock/fundamental/${symbol}`)
export const getStockTechnical = (symbol, period = 'day') => http.get(`/stock/technical/${symbol}`, { params: { period } })
export const searchStock = (keyword) => http.get('/stock/search', { params: { keyword } })

// 评分引擎
export const getStockScore = (symbol) => http.get(`/score/${symbol}`)
export const getScoreTop = (params) => http.get('/score/batch/top', { params })
export const getScoreBottom = (params) => http.get('/score/batch/bottom', { params })
export const getScoreBySignal = (params) => http.get('/score/batch/signal', { params })

// 资金/板块（当前环境不可用）
export const getNorthboundFlow = () => Promise.resolve({ data: [] })
export const getMainFlow = () => Promise.resolve({ data: [] })
export const getIndustryFlow = () => Promise.resolve({ data: [] })
export const getConceptFlow = () => Promise.resolve({ data: [] })
export const getNorthboundHoldings = () => Promise.resolve({ data: [] })
