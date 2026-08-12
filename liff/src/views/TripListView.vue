<template>
  <div>
    <h1 class="text-xl font-bold mb-4">🧳 旅行列表</h1>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="trips.length === 0" class="text-center py-8 text-gray-400">尚無旅行紀錄</div>
    <div v-else class="space-y-3">
      <router-link v-for="t in trips" :key="t.id" :to="`/trips/${t.id}`"
                   class="block bg-white rounded-xl shadow p-4">
        <div class="flex items-center gap-2">
          <span class="text-2xl">{{ t.badge_emoji }}</span>
          <div class="flex-1">
            <p class="font-semibold">{{ t.title }}</p>
            <p class="text-xs text-gray-400">{{ t.location }}</p>
          </div>
          <span class="text-xs px-2 py-1 rounded-full"
                :class="t.status === 'ended' ? 'bg-gray-100 text-gray-500' : 'bg-blue-100 text-blue-600'">
            {{ t.status === 'ended' ? '已結束' : '進行中' }}
          </span>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'

const trips = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try { trips.value = await api.trips() }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>