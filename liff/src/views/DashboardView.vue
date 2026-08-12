<template>
  <div>
    <h1 class="text-xl font-bold mb-4">📊 群組儀表板</h1>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="data">
      <div class="grid grid-cols-2 gap-3 mb-6">
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">{{ data.summary.total_messages }}</p>
          <p class="text-xs text-gray-500">總訊息</p>
        </div>
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">{{ data.summary.member_count }}</p>
          <p class="text-xs text-gray-500">成員數</p>
        </div>
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">{{ data.summary.active_trips }}</p>
          <p class="text-xs text-gray-500">進行中旅行</p>
        </div>
        <div class="bg-white rounded-xl p-4 shadow text-center">
          <p class="text-2xl font-bold">{{ data.summary.active_days }}</p>
          <p class="text-xs text-gray-500">活躍天數</p>
        </div>
      </div>

      <h2 class="font-semibold mb-2">🏆 Top 話癆</h2>
      <div class="bg-white rounded-xl shadow divide-y mb-6">
        <div v-for="(u, i) in data.top_users.slice(0, 5)" :key="u.user_id"
             class="flex items-center px-4 py-2 gap-3">
          <span class="text-gray-400 text-sm w-5">{{ i + 1 }}</span>
          <span class="flex-1 text-sm">{{ u.user_name || u.user_id }}</span>
          <span class="text-sm font-medium">{{ u.total }}</span>
        </div>
      </div>

      <h2 class="font-semibold mb-2">📨 訊息類型</h2>
      <div class="bg-white rounded-xl shadow divide-y">
        <div v-for="t in data.type_distribution" :key="t.type"
             class="flex items-center px-4 py-2 gap-3">
          <span class="flex-1 text-sm">{{ t.type }}</span>
          <span class="text-sm font-medium">{{ t.count }}</span>
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

onMounted(async () => {
  try { data.value = await api.dashboard() }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>