import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
  { path: '/market', name: 'Market', component: () => import('../views/MarketView.vue') },
  { path: '/stock/:code', name: 'StockDetail', component: () => import('../views/StockDetail.vue') },
  { path: '/score', name: 'ScoreRank', component: () => import('../views/ScoreRank.vue') },
  // { path: '/capital', name: 'Capital', component: () => import('../views/CapitalView.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router