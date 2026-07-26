<template>
  <div class="min-h-screen bg-bg text-gray-200">
    <!-- 顶部导航 -->
    <nav class="bg-card border-b border-border sticky top-0 z-50">
      <div class="max-w-[1600px] mx-auto px-4 h-12 flex items-center justify-between">
        <div class="flex items-center gap-6">
          <router-link to="/" class="font-bold text-accent text-sm tracking-wide">A股评分系统</router-link>
          <div class="hidden md:flex gap-1">
            <router-link v-for="item in navItems" :key="item.path" :to="item.path"
              class="px-3 py-1 rounded text-xs transition-colors"
              :class="$route.path === item.path || (item.path !== '/' && $route.path.startsWith(item.path)) ? 'bg-accent/15 text-accent' : 'text-muted hover:text-gray-200'">
              {{ item.label }}
            </router-link>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <div class="relative">
            <input v-model="keyword" @keyup.enter="doSearch" @focus="showSearch = true" @blur="hideSearch"
              placeholder="输入代码或名称"
              class="bg-bg border border-border rounded px-3 py-1 text-xs w-40 focus:w-56 transition-all focus:outline-none focus:border-accent/50"/>
            <div v-if="showSearch && searchResults.length" class="absolute top-full mt-1 left-0 right-0 bg-card border border-border rounded shadow-lg z-50">
              <div v-for="r in searchResults" :key="r.code" @mousedown.prevent="goStock(r.code)"
                class="px-3 py-2 text-xs hover:bg-white/5 cursor-pointer flex justify-between">
                <span>{{ r.name }}</span>
                <span class="text-muted font-mono">{{ r.code }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </nav>

    <main class="max-w-[1600px] mx-auto px-4 py-4">
      <router-view/>
    </main>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { searchStock } from './api'

const router = useRouter()
const route = useRoute()

const navItems = [
  { path: '/', label: '首页' },
  { path: '/market', label: '市场行情' },
  { path: '/score', label: '评分排行' },
  { path: '/capital', label: '资金流向' },
]

const keyword = ref('')
const showSearch = ref(false)
const searchResults = ref([])

let searchTimer = null
watch(keyword, (v) => {
  clearTimeout(searchTimer)
  if (!v.trim()) { searchResults.value = []; return }
  searchTimer = setTimeout(async () => {
    try {
      const { data } = await searchStock(v.trim())
      searchResults.value = data || []
    } catch { searchResults.value = [] }
  }, 300)
})

function doSearch() {
  if (keyword.value.trim()) {
    const kw = keyword.value.trim()
    // 如果搜索结果只有一条或精确匹配代码，直接跳转
    if (searchResults.value.length === 1) {
      goStock(searchResults.value[0].code)
    } else if (/^\d{6}$/.test(kw)) {
      goStock(kw)
    }
  }
}

function goStock(code) {
  showSearch.value = false
  router.push(`/stock/${code}`)
}

function hideSearch() {
  setTimeout(() => { showSearch.value = false }, 200)
}
</script>

<style>
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --bg: #0d1117;
  --card: #161b22;
  --border: #21262d;
  --accent: #58a6ff;
  --muted: #8b949e;
  --rise: #ef4444;
  --fall: #22c55e;
}

body {
  background: var(--bg);
  margin: 0;
}

.bg-bg { background: var(--bg); }
.bg-card { background: var(--card); }
.border-border { border-color: var(--border); }
.text-accent { color: var(--accent); }
.text-muted { color: var(--muted); }
.text-rise { color: var(--rise); }
.text-fall { color: var(--fall); }
.hover\:bg-white\/3:hover { background: rgba(255,255,255,0.03); }
.hover\:bg-white\/5:hover { background: rgba(255,255,255,0.05); }
.focus\:border-accent\/50:focus { border-color: rgba(88,166,255,0.5); }

.fade-in { animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

.loading-spinner {
  width: 32px; height: 32px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>