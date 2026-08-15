<template>
  <div class="min-h-screen bg-surface-subtle pb-24 text-slate-800">
    <!-- Admin group switcher -->
    <div v-if="auth.role === 'admin'" class="sticky top-0 z-30 bg-accent-50/90 backdrop-blur-md border-b border-accent-200/80 px-4 py-2 flex items-center gap-2">
      <span class="text-xs font-semibold text-accent-700 shrink-0">🔧 切換群組</span>
      <select v-model="adminGroup" @change="onAdminGroupChange"
              class="flex-1 text-xs bg-white border border-accent-300 rounded-xl px-2.5 py-1.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-accent-400">
        <option v-for="g in adminGroups" :key="g.group_id" :value="g.group_id">
          {{ g.name }} ({{ g.msg_count }})
        </option>
      </select>
    </div>
    <!-- Period selector -->
    <PeriodSelector v-if="auth.initialized" />
    
    <main class="p-4 max-w-lg mx-auto">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <!-- More drawer backdrop + panel -->
    <Transition name="more-sheet">
      <div v-if="showMore" class="fixed inset-0 z-40 bg-slate-900/20 backdrop-blur-xs" @click.self="showMore = false">
        <div class="absolute bottom-[76px] inset-x-0 mx-3 bg-white/95 backdrop-blur-xl rounded-2xl shadow-pop
                    border border-slate-200/80 p-4">
          <div class="flex items-center justify-between mb-3 px-1">
            <p class="text-xs text-slate-400 font-bold tracking-wide uppercase">更多功能與工具</p>
            <button @click="showMore = false" class="text-slate-400 hover:text-slate-600 text-xs px-1.5 py-0.5 rounded">
              ✕
            </button>
          </div>
          <div class="grid grid-cols-4 gap-2">
            <router-link
              v-for="item in moreItems" :key="item.to"
              :to="item.to"
              class="flex flex-col items-center gap-1.5 py-3 rounded-xl transition-all duration-150 text-slate-500
                     btn-press"
              :class="route.path === item.to ? 'text-brand-600 bg-brand-50/80 font-semibold' : 'hover:bg-slate-50 hover:text-slate-700'"
              @click="showMore = false"
            >
              <div class="w-8 h-8 rounded-lg flex items-center justify-center" :class="route.path === item.to ? 'bg-brand-100/80' : 'bg-slate-100/70'">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path :d="item.icon" />
                </svg>
              </div>
              <span class="text-[11px]">{{ item.label }}</span>
            </router-link>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Bottom nav -->
    <nav v-if="auth.initialized"
         class="fixed bottom-0 inset-x-0 z-50 bg-white/85 backdrop-blur-lg border-t border-slate-200/80
                safe-area-pb shadow-lg">
      <div class="flex justify-around max-w-lg mx-auto px-2 py-1">
        <router-link
          v-for="item in primaryItems" :key="item.to"
          :to="item.to"
          class="flex flex-col items-center gap-0.5 px-3 py-1.5 min-w-[56px] rounded-xl transition-all duration-200
                 btn-press text-slate-400"
          :class="isActive(item.to) ? 'text-brand-600 font-semibold' : 'hover:text-slate-600'"
        >
          <div class="relative p-1 rounded-xl transition-colors" :class="isActive(item.to) ? 'bg-brand-50' : ''">
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path :d="item.icon" />
            </svg>
            <span v-if="isActive(item.to)"
                  class="absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-brand-600 shadow-sm" />
          </div>
          <span class="text-[10px] tracking-tight">{{ item.label }}</span>
        </router-link>

        <!-- More button -->
        <button
          class="flex flex-col items-center gap-0.5 px-3 py-1.5 min-w-[56px] rounded-xl transition-all duration-200
                 btn-press"
          :class="isMoreActive || showMore ? 'text-brand-600 font-semibold' : 'text-slate-400 hover:text-slate-600'"
          @click="showMore = !showMore"
        >
          <div class="relative p-1 rounded-xl transition-colors" :class="isMoreActive || showMore ? 'bg-brand-50' : ''">
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M6.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0zm6 0a.75.75 0 11-1.5 0
                       .75.75 0 011.5 0zm6 0a.75.75 0 11-1.5 0 .75.75 0 011.5 0z" />
            </svg>
            <span v-if="isMoreActive"
                  class="absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-brand-600 shadow-sm" />
          </div>
          <span class="text-[10px] tracking-tight">更多</span>
        </button>
      </div>
    </nav>

    <!-- 全域 Toast -->
    <Toast />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { api, setAdminGroup, getAdminGroup } from '@/api/client'
import PeriodSelector from '@/components/PeriodSelector.vue'
import Toast from '@/components/Toast.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const showMore = ref(false)

const adminGroups = ref<any[]>([])
const adminGroup = ref('')

watch(() => auth.role, async (role) => {
  if (role !== 'admin') return
  try {
    adminGroups.value = await api.adminGroups()
    if (adminGroups.value.length) {
      // Prefer stored selection; fall back to most active
      const stored = getAdminGroup()
      const valid = stored && adminGroups.value.find(g => g.group_id === stored)
      adminGroup.value = valid ? stored : adminGroups.value[0].group_id
      setAdminGroup(adminGroup.value)
    }
  } catch {}
}, { immediate: true })

function onAdminGroupChange() {
  setAdminGroup(adminGroup.value)
  // Reload current view
  router.go(0)
}

const primaryItems = computed(() => {
  const base = [
    {
      to: '/',
      label: '儀表板',
      icon: 'M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z',
    },
    {
      to: '/leaderboard',
      label: '排行榜',
      icon: 'M16.5 18.75h-9m9 0a3 3 0 013 3h-15a3 3 0 013-3m9 0v-3.375c0-.621-.503-1.125-1.125-1.125h-.871M7.5 18.75v-3.375c0-.621.504-1.125 1.125-1.125h.872m5.007 0H9.497m5.007 0a7.454 7.454 0 01-.982-3.172M9.497 14.25a7.454 7.454 0 00.981-3.172M5.25 4.236c-.982.143-1.954.317-2.916.52A6.003 6.003 0 007.73 9.728M5.25 4.236V4.5c0 2.108.966 3.99 2.48 5.228M5.25 4.236V2.721C7.456 2.41 9.71 2.25 12 2.25c2.291 0 4.545.16 6.75.47v1.516M7.73 9.728a6.726 6.726 0 002.748 1.35m8.272-6.842V4.5c0 2.108-.966 3.99-2.48 5.228m2.48-5.492a46.32 46.32 0 012.916.52 6.003 6.003 0 01-5.395 4.972m0 0a6.726 6.726 0 01-2.749 1.35m0 0a6.772 6.772 0 01-3.044 0',
    },
    {
      to: '/timeline',
      label: '回憶',
      icon: 'M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z',
    },
    {
      to: '/profile',
      label: '個人',
      icon: 'M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z',
    },
  ]
  return base
})

const moreRoutes = ['/badges', '/trips', '/map', '/interactions', '/topics', '/pulse', '/compare', '/admin']

const moreItems = computed(() => {
  const items = [
    {
      to: '/trips',
      label: '旅行',
      icon: 'M15 10.5a3 3 0 11-6 0 3 3 0 016 0zM19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z',
    },
    {
      to: '/badges',
      label: '徽章',
      icon: 'M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.562.562 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z',
    },
    {
      to: '/map',
      label: '足跡',
      icon: 'M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V18.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z',
    },
    {
      to: '/interactions',
      label: '互動',
      icon: 'M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z',
    },
    {
      to: '/topics',
      label: '話題',
      icon: 'M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3zM6 6h.008v.008H6V6z',
    },
    {
      to: '/pulse',
      label: '動態',
      icon: 'M3.75 12h4.5l1.5-6 3 12 1.5-6h4.5',
    },
    {
      to: '/compare',
      label: '對比',
      icon: 'M9 4.5v15m6-15v15M4.5 9h4.5m6 6h4.5M4.5 15h4.5m6-6h4.5',
    },
  ]
  if (auth.role === 'admin') {
    items.push({
      to: '/admin',
      label: '管理',
      icon: 'M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.282c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28zM15 12a3 3 0 11-6 0 3 3 0 016 0z',
    })
  }
  return items
})

const isMoreActive = computed(() => moreRoutes.includes(route.path))

function isActive(to: string) {
  if (to === '/') return route.path === '/'
  return route.path.startsWith(to)
}
</script>
