<template>
  <div class="fade-in space-y-4">
    <div class="bg-card border border-border rounded-lg p-4">
      <div class="flex items-center justify-between flex-wrap gap-3">
        <h2 class="text-lg font-bold">评分排行榜</h2>
        <div class="flex gap-2 flex-wrap">
          <button v-for="tab in tabs" :key="tab.key" @click="switchTab(tab.key)"
            :class="activeTab === tab.key ? 'bg-accent/20 text-accent' : 'bg-white/5 text-muted hover:text-gray-200'"
            class="px-3 py-1 rounded text-xs transition-colors">
            {{ tab.label }}
          </button>
          <select v-if="activeTab === 'signal'" v-model="signalType"
            class="bg-bg border border-border rounded px-2 py-1 text-xs text-gray-300"
            @change="loadData">
            <option v-for="s in signalOptions" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
      </div>
    </div>

    <!-- 评分分布概览 -->
    <div v-if="stats.total > 0" class="bg-card border border-border rounded-lg p-4">
      <div class="grid grid-cols-3 md:grid-cols-5 gap-3 text-center text-sm">
        <div class="p-2 bg-bg rounded-lg">
          <div class="text-muted text-xs">评分股票数</div>
          <div class="text-lg font-bold mt-1">{{ stats.total }}</div>
        </div>
        <div class="p-2 bg-emerald-500/10 rounded-lg">
          <div class="text-emerald-400 text-xs">强烈买入/买入</div>
          <div class="text-lg font-bold text-emerald-400 mt-1">{{ stats.buyCount }}</div>
        </div>
        <div class="p-2 bg-amber-500/10 rounded-lg">
          <div class="text-amber-400 text-xs">观望</div>
          <div class="text-lg font-bold text-amber-400 mt-1">{{ stats.watchCount }}</div>
        </div>
        <div class="p-2 bg-red-500/10 rounded-lg">
          <div class="text-red-400 text-xs">卖出/强烈卖出</div>
          <div class="text-lg font-bold text-red-400 mt-1">{{ stats.sellCount }}</div>
        </div>
        <div class="p-2 bg-bg rounded-lg">
          <div class="text-muted text-xs">缓存状态</div>
          <div class="text-sm mt-1" :class="cacheStatus === 'ready' ? 'text-emerald-400' : 'text-amber-400'">
            {{ cacheStatus === 'ready' ? '就绪' : '加载中...' }}
          </div>
        </div>
      </div>
    </div>

    <!-- 数据表格 -->
    <div class="bg-card border border-border rounded-lg overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-border text-muted text-xs">
            <th class="text-left py-2.5 px-3">排名</th>
            <th class="text-left py-2.5 px-3">代码</th>
            <th class="text-left py-2.5 px-3">名称</th>
            <th class="text-right py-2.5 px-3">综合评分</th>
            <th class="text-center py-2.5 px-3">信号</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, idx) in tableData" :key="item.code"
            class="border-b border-border/50 hover:bg-white/3 cursor-pointer transition-colors"
            @click="goDetail(item.code)">
            <td class="py-2 px-3 text-muted font-mono text-xs">{{ activeTab === 'bottom' ? stats.total - idx : idx + 1 }}</td>
            <td class="py-2 px-3 font-mono text-xs text-accent">{{ item.code }}</td>
            <td class="py-2 px-3">{{ item.name }}</td>
            <td class="py-2 px-3 text-right">
              <span class="font-bold" :class="item.total_score >= 65 ? 'text-emerald-400' : item.total_score >= 45 ? 'text-amber-400' : 'text-red-400'">
                {{ item.total_score }}
              </span>
            </td>
            <td class="py-2 px-3 text-center">
              <span class="px-2 py-0.5 rounded-full text-xs"
                :class="item.signal.includes('买入') ? 'bg-emerald-500/20 text-emerald-400' :
                       item.signal.includes('卖出') ? 'bg-red-500/20 text-red-400' :
                       'bg-amber-500/20 text-amber-400'">
                {{ item.signal }}
              </span>
            </td>
          </tr>
          <tr v-if="!tableData.length">
            <td colspan="5" class="py-12 text-center text-muted">
              {{ cacheStatus === 'loading' ? '行情数据加载中，请稍后...' : '暂无数据' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getScoreTop, getScoreBottom, getScoreBySignal } from '../api'

const router = useRouter()

const tabs = [
  { key: 'top', label: '评分 Top 50' },
  { key: 'bottom', label: '评分 Bottom 50' },
  { key: 'signal', label: '按信号筛选' },
]
const signalOptions = ['强烈买入', '买入', '观望', '卖出', '强烈卖出']

const activeTab = ref('top')
const signalType = ref('买入')
const tableData = ref([])
const cacheStatus = ref('loading')
const stats = reactive({ total: 0, buyCount: 0, watchCount: 0, sellCount: 0 })

async function loadData() {
  try {
    let res
    if (activeTab.value === 'top') {
      res = await getScoreTop({ limit: 50 })
    } else if (activeTab.value === 'bottom') {
      res = await getScoreBottom({ limit: 50 })
    } else {
      res = await getScoreBySignal({ signal: signalType.value, limit: 50 })
    }
    const d = res.data
    tableData.value = d.data || []
    cacheStatus.value = d.cache_status || 'unknown'
    stats.total = d.total || 0
    // 简单统计
    stats.buyCount = tableData.value.filter(i => i.signal.includes('买入')).length
    stats.watchCount = tableData.value.filter(i => i.signal === '观望').length
    stats.sellCount = tableData.value.filter(i => i.signal.includes('卖出')).length
  } catch (e) {
    console.error(e)
    cacheStatus.value = 'error'
  }
}

function switchTab(tab) {
  activeTab.value = tab
  loadData()
}

function goDetail(code) {
  router.push(`/stock/${code}`)
}

onMounted(() => loadData())
</script>