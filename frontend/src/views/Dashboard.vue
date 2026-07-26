<template>
  <div class="fade-in space-y-4">
    <!-- 大盘指数卡片 -->
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      <div v-for="idx in overview.indices" :key="idx.code"
        class="bg-card border border-border rounded-lg p-3 hover:border-accent/40 transition-colors cursor-default">
        <div class="text-xs text-muted mb-1">{{ idx.name }}</div>
        <div class="text-lg font-bold" :class="idx.change_pct >= 0 ? 'text-rise' : 'text-fall'">
          {{ idx.price }}
        </div>
        <div class="text-sm font-medium" :class="idx.change_pct >= 0 ? 'text-rise' : 'text-fall'">
          {{ idx.change_pct >= 0 ? '+' : '' }}{{ idx.change_pct }}%
        </div>
      </div>
      <div v-if="!overview.indices.length" class="col-span-full text-center text-muted py-6">指数加载中...</div>
    </div>

    <!-- 市场统计 -->
    <div v-if="overview.stats.total" class="grid grid-cols-3 md:grid-cols-7 gap-3">
      <StatCard label="上涨" :value="overview.stats.up_count" color="text-rise" />
      <StatCard label="下跌" :value="overview.stats.down_count" color="text-fall" />
      <StatCard label="平盘" :value="overview.stats.flat_count" color="text-muted" />
      <StatCard label="涨停" :value="overview.stats.limit_up" color="text-orange-400" />
      <StatCard label="跌停" :value="overview.stats.limit_down" color="text-blue-400" />
      <StatCard label="平均涨幅" :value="overview.stats.avg_change_pct + '%'" :color="overview.stats.avg_change_pct >= 0 ? 'text-rise' : 'text-fall'" />
      <StatCard label="总成交额" :value="formatAmount(overview.stats.total_amount)" color="text-accent" />
    </div>
    <div v-else class="bg-card border border-border rounded-lg p-6 text-center text-muted">
      股票数据加载中，首次需扫描约14000个代码，请稍候...
    </div>

    <!-- 图表区 -->
    <div class="bg-card border border-border rounded-lg p-4">
      <h3 class="text-sm font-semibold text-muted mb-3">沪深300走势</h3>
      <div ref="indexChartRef" class="h-72"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getMarketOverview, getIndexKline } from '../api'

const overview = ref({ indices: [], stats: {} })
const indexChartRef = ref(null)
let charts = []

function formatAmount(v) {
  if (!v || v < 1e8) return (v / 1e4).toFixed(0) + '万'
  return (v / 1e8).toFixed(1) + '亿'
}

onMounted(async () => {
  try {
    const { data } = await getMarketOverview()
    overview.value = data
  } catch (e) { console.error(e) }

  await nextTick()

  // 沪深300 K线
  try {
    const { data: klineData } = await getIndexKline('000300')
    if (klineData.length && indexChartRef.value) {
      const chart = echarts.init(indexChartRef.value, 'dark')
      charts.push(chart)
      chart.setOption({
        backgroundColor: 'transparent',
        textStyle: { color: '#8b949e' },
        tooltip: { trigger: 'axis' },
        grid: [{ left: '8%', right: '3%', top: '10%', height: '55%' }, { left: '8%', right: '3%', top: '72%', height: '20%' }],
        xAxis: [
          { type: 'category', data: klineData.map(d => d.date), gridIndex: 0, axisLabel: { fontSize: 10 } },
          { type: 'category', data: klineData.map(d => d.date), gridIndex: 1, axisLabel: { show: false } },
        ],
        yAxis: [
          { type: 'value', gridIndex: 0, scale: true, splitLine: { lineStyle: { color: '#21262d' } } },
          { type: 'value', gridIndex: 1, scale: true, splitLine: { show: false } },
        ],
        dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 }],
        series: [
          { name: '沪深300', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: klineData.map(d => d.close), lineStyle: { color: '#58a6ff', width: 1.5 }, symbol: 'none', areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(88,166,255,0.2)' }, { offset: 1, color: 'rgba(88,166,255,0)' }]) } },
          { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: klineData.map(d => d.volume), itemStyle: { color: '#30363d' }, barMaxWidth: 3 },
        ],
      })
    }
  } catch (e) { console.error(e) }

  window.addEventListener('resize', () => charts.forEach(c => c.resize()))
})

onBeforeUnmount(() => { charts.forEach(c => c.dispose()); charts = [] })
</script>

<script>
export default {
  components: {
    StatCard: {
      props: ['label', 'value', 'color'],
      template: `
        <div class="bg-card border border-border rounded-lg p-3 text-center">
          <div class="text-xs text-muted">{{ label }}</div>
          <div class="text-lg font-bold mt-1" :class="color">{{ value }}</div>
        </div>
      `,
    },
  },
}
</script>
