<template>
  <div>
    <h1 class="text-xl font-bold mb-4 text-gray-900">群組動態</h1>

    <!-- Skeleton -->
    <div v-if="loading">
      <div class="skeleton h-4 w-24 rounded-full mb-3" />
      <div class="skeleton rounded-2xl mb-6" style="height:120px" />
      <div class="skeleton h-4 w-24 rounded-full mb-3" />
      <div class="skeleton rounded-2xl mb-6" style="height:160px" />
    </div>

    <div v-else-if="error" class="flex flex-col items-center py-16 text-center gap-2">
      <p class="text-3xl">⚠️</p>
      <p class="text-sm font-medium text-gray-700">無法載入資料</p>
      <p class="text-xs text-gray-400">{{ error }}</p>
    </div>

    <div v-else-if="data">
      <!-- 回應速度 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">群組回應速度</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6">
        <div class="flex items-baseline gap-2 mb-1">
          <span class="text-2xl font-bold tabular-nums text-blue-700">
            {{ data.response_speed.avg_minutes !== null ? data.response_speed.avg_minutes : '—' }}
          </span>
          <span class="text-sm text-gray-500">分鐘 · 平均回應時間</span>
        </div>
        <p v-if="!data.response_speed.fastest_responders.length" class="text-xs text-gray-400 mt-2">
          目前還沒有足夠的回覆資料
        </p>
        <div v-else class="mt-3 divide-y">
          <p class="text-xs text-gray-400 mb-1">⚡ 閃電回覆王</p>
          <div v-for="(u, i) in data.response_speed.fastest_responders" :key="u.user_id"
               class="flex items-center py-2 gap-3">
            <span class="text-gray-300 text-sm w-5 tabular-nums font-medium">{{ i + 1 }}</span>
            <span class="flex-1 text-sm text-gray-800 truncate">{{ u.name }}</span>
            <span class="text-sm font-semibold tabular-nums text-blue-600">{{ u.avg_minutes }} 分</span>
          </div>
        </div>
      </div>

      <!-- 訊息爆發 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">訊息爆發時段</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 mb-6 overflow-hidden">
        <p class="text-xs text-gray-400 px-4 pt-3">平均每小時 {{ data.avg_hourly }} 則</p>
        <div v-if="!data.bursts.length" class="px-4 py-6 text-center text-xs text-gray-400">
          尚無明顯爆發時段
        </div>
        <div v-else class="divide-y mt-1">
          <div v-for="(b, i) in data.bursts" :key="b.hour" class="flex items-center px-4 py-3 gap-3">
            <span class="text-gray-300 text-sm w-5 tabular-nums font-medium">{{ i + 1 }}</span>
            <span class="flex-1 text-sm text-gray-700 tabular-nums">{{ b.hour }}:00</span>
            <span class="text-amber-500 text-xs">{{ '⚡'.repeat(Math.min(3, Math.round(b.ratio))) }}</span>
            <span class="text-sm font-semibold tabular-nums text-gray-700">{{ b.count }} 則</span>
          </div>
        </div>
      </div>

      <!-- 潛水員 -->
      <h2 class="font-semibold text-sm text-gray-500 uppercase tracking-wide mb-2">潛水員偵測</h2>
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div v-if="!data.lurkers.length" class="px-4 py-6 text-center text-xs text-gray-400">
          🎉 沒有人潛水，全員活躍中！
        </div>
        <div v-else class="divide-y">
          <div v-for="u in data.lurkers" :key="u.user_id" class="flex items-center px-4 py-3 gap-3">
            <span class="text-lg">🙈</span>
            <span class="flex-1 text-sm text-gray-800 truncate">{{ u.name }}</span>
            <span class="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 tabular-nums">
              {{ u.days_inactive !== null ? `${u.days_inactive} 天未發言` : '從未發言' }}
            </span>
          </div>
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

onMounted(async () => {
  try { data.value = await api.pulse() }
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
  finally { loading.value = false }
})
</script>
