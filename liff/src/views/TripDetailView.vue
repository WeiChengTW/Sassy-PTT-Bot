<template>
  <div>
    <button @click="$router.back()" class="text-sm text-gray-500 mb-4">← 返回</button>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="detail">
      <div class="bg-white rounded-xl shadow p-4 mb-4">
        <h1 class="text-xl font-bold">{{ detail.trip.title }}</h1>
        <p class="text-gray-500 text-sm">{{ detail.trip.location }}</p>
        <p class="text-xs text-gray-400 mt-1">狀態：{{ detail.trip.status }}</p>
        <p class="text-xs text-gray-400">訊息數：{{ detail.stats.message_count }}</p>
      </div>

      <h2 class="font-semibold mb-2">👥 參與者（{{ detail.participants.length }}）</h2>
      <div class="bg-white rounded-xl shadow divide-y mb-4">
        <div v-for="p in detail.participants" :key="p.user_id" class="px-4 py-2 text-sm">
          {{ p.user_name || p.user_id }}
          <span class="text-xs text-gray-400 ml-2">{{ p.role || '成員' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'

const route = useRoute()
const detail = ref<any>(null)
const loading = ref(true)

onMounted(async () => {
  try { detail.value = await api.tripDetail(route.params.id as string) }
  catch (e) { console.error(e) }
  finally { loading.value = false }
})
</script>