<template>
  <div>
    <h1 class="text-xl font-bold mb-4 text-gray-900">群組儀表板</h1>

    <!-- Skeleton -->
    <div v-if="loading">
      <div class="grid grid-cols-2 gap-3 mb-6">
        <div v-for="i in 4" :key="i" class="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
          <div class="skeleton h-8 w-16 rounded mb-2" />
          <div class="skeleton h-3 w-12 rounded-full" />
        </div>
      </div>
      <div class="skeleton h-4 w-24 rounded-full mb-3" />
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y">
        <div v-for="i in 5" :key="i" class="flex items-center px-4 py-3 gap-3">
          <div class="skeleton w-5 h-4 rounded" />
          <div class="skeleton flex-1 h-4 rounded-full" />
          <div class="skeleton w-10 h-4 rounded" />
        </div>
      </div>
    </div>

    <div v-else-if="error" class="flex flex-col items-center py-16 text-center gap-2">
      <p class="text-3xl">⚠️</p>
      <p class="text-sm font-medium text-gray-700">無法載入資料</p>
      <p class="text-xs text-gray-400">{{ error }}</p>
    </div>
    <div v-else-if="data">
      <!-- Stat cards -->
      <div class="grid grid-cols-2 gap-3 mb-6">
        <div class="bg-blue-50 border border-blue-100 rounded-2xl p-4 shadow-sm">
          <p class="text-2xl font-bold tabular-nums text-blue-700">
            {{ data.summary.total_messages.toLocaleString() }}
          </p>
          <p class="text-xs text-blue-500 mt-0.5">總訊息</p>
        </div>
        <div class="bg-emerald-50 border border-emerald-100 rounded-2xl p-4 shadow-sm">
          <p class="text-2xl font-bold tabular-nums text-emerald-700">
            {{ data.summary.member_count }}
          </p>
          <p class="text-xs text-emerald-500 mt-0.5">成員數</p>
        </div>
        <div class="bg-violet-50 border border-violet-100 rounded-2xl p-4 shadow-sm">
          <p class="text-2xl font-bold tabular-nums text-violet-700">
            {{ data.summary.active_trips }}
          </p>
          <p class="text-xs text-violet-500 mt-0.5">進行中旅行</p>
        </div>
        <div class="bg-amber-50 border border-amber-100 rounded-2xl p-4 shadow-sm">
          <p class="text-2xl font-bold tabular-nums text-amber-700">
            {{ data.summary.active_days }}
          </p>
          <p class="text-xs text-amber-500 mt-0.5">活躍天數</p>
        </div>
      </div>

      <!-- Top users -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">Top 話癆</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y mb-6 overflow-hidden">
        <div v-for="(u, i) in data.top_users.slice(0, 5)" :key="u.user_id"
             class="flex items-center px-4 py-3 gap-3">
          <span class="text-gray-300 text-sm w-5 tabular-nums font-medium">{{ i + 1 }}</span>
          <span class="flex-1 text-sm text-gray-800 truncate">{{ u.user_name || u.user_id }}</span>
          <span class="text-sm font-semibold tabular-nums text-gray-700">{{ u.total.toLocaleString() }}</span>
        </div>
      </div>

      <!-- Message type breakdown -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">訊息類型</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y overflow-hidden">
        <div v-for="t in data.type_distribution" :key="t.type"
             class="flex items-center px-4 py-3 gap-3">
          <span class="w-2 h-2 rounded-full flex-shrink-0" :style="{ background: TYPE_COLORS[t.type] || '#94a3b8' }" />
          <span class="flex-1 text-sm text-gray-700 capitalize">{{ t.type }}</span>
          <span class="text-sm font-semibold tabular-nums text-gray-600">{{ t.count.toLocaleString() }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'

const data = ref<any>(null)
const loading = ref(true)
const error = ref('')

const TYPE_COLORS: Record<string, string> = {
  text: '#60a5fa', sticker: '#f472b6', image: '#34d399',
  video: '#fb923c', audio: '#a78bfa', file: '#94a3b8',
}

onMounted(async () => {
  try { data.value = await api.dashboard() }
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
  finally { loading.value = false }
})
</script>
