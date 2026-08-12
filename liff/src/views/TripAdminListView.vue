<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-xl font-bold">🛠️ 旅行管理</h1>
      <router-link to="/admin/trips/new"
                   class="bg-blue-600 text-white text-sm px-3 py-1.5 rounded-lg">
        + 新增旅行
      </router-link>
    </div>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else class="space-y-3">
      <router-link v-for="t in trips" :key="t.id" :to="`/admin/trips/${t.id}`"
                   class="block bg-white rounded-xl shadow p-4">
        <div class="flex items-center gap-2">
          <span class="text-2xl">{{ t.badge_emoji }}</span>
          <div class="flex-1">
            <p class="font-semibold">{{ t.title }}</p>
            <p class="text-xs text-gray-400">{{ t.location }}</p>
          </div>
          <span class="text-xs text-gray-500">{{ t.status }}</span>
        </div>
      </router-link>
      <div v-if="trips.length === 0" class="text-center py-8 text-gray-400">尚無旅行</div>
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
