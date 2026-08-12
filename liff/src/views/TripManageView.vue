<template>
  <div>
    <button @click="$router.back()" class="text-sm text-gray-500 mb-4">← 返回</button>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="detail">
      <div class="bg-white rounded-xl shadow p-4 mb-4">
        <h1 class="text-xl font-bold">{{ detail.trip.title }}</h1>
        <p class="text-gray-500 text-sm">{{ detail.trip.location }}</p>
        <p class="text-xs mt-1">狀態：
          <span :class="detail.trip.status === 'ended' ? 'text-gray-400' : 'text-blue-600'">
            {{ detail.trip.status === 'ended' ? '已結束' : '進行中' }}
          </span>
        </p>
      </div>

      <div class="bg-white rounded-xl shadow p-4 mb-4">
        <h2 class="font-semibold mb-2">👥 參與者（{{ detail.participants.length }}）</h2>
        <div class="text-sm text-gray-600 mb-3">
          <span v-for="p in detail.participants" :key="p.user_id"
                class="inline-block bg-gray-100 rounded-full px-2 py-0.5 text-xs mr-1 mb-1">
            {{ p.user_name || p.user_id }}
          </span>
        </div>
        <div v-if="detail.trip.status !== 'ended'" class="flex gap-2">
          <input v-model="newParticipant" placeholder="LINE user_id"
                 class="flex-1 border rounded-lg px-3 py-1.5 text-sm" />
          <button @click="addParticipant" :disabled="addLoading"
                  class="bg-gray-800 text-white text-sm px-3 py-1.5 rounded-lg disabled:opacity-50">
            加入
          </button>
        </div>
      </div>

      <div v-if="detail.trip.status !== 'ended'" class="space-y-3">
        <button @click="endTrip" :disabled="actionLoading"
                class="w-full bg-orange-500 text-white rounded-xl py-3 font-medium disabled:opacity-50">
          🏁 結束旅行
        </button>
      </div>
      <div v-if="detail.trip.status === 'ended'" class="space-y-3">
        <button @click="awardBadges" :disabled="actionLoading"
                class="w-full bg-purple-600 text-white rounded-xl py-3 font-medium disabled:opacity-50">
          🏅 發放徽章
        </button>
      </div>

      <p v-if="message" class="text-center mt-3 text-sm text-green-600">{{ message }}</p>
      <p v-if="error" class="text-center mt-3 text-sm text-red-500">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'

const route = useRoute()
const tripId = route.params.id as string

const detail = ref<any>(null)
const loading = ref(true)
const addLoading = ref(false)
const actionLoading = ref(false)
const newParticipant = ref('')
const message = ref('')
const error = ref('')

async function load() {
  loading.value = true
  try { detail.value = await api.tripDetail(tripId) }
  finally { loading.value = false }
}

async function addParticipant() {
  if (!newParticipant.value.trim()) return
  addLoading.value = true
  try {
    await api.adminAddParticipants(tripId, [newParticipant.value.trim()])
    newParticipant.value = ''
    await load()
    message.value = '已加入'
  } catch (e: any) { error.value = e.message }
  finally { addLoading.value = false }
}

async function endTrip() {
  if (!confirm('確定結束旅行？')) return
  actionLoading.value = true
  try {
    await api.adminEndTrip(tripId)
    await load()
    message.value = '旅行已結束'
  } catch (e: any) { error.value = e.message }
  finally { actionLoading.value = false }
}

async function awardBadges() {
  actionLoading.value = true
  try {
    const res = await api.adminAwardBadges(tripId)
    message.value = `已發放 ${res.awarded.length} 枚徽章`
  } catch (e: any) { error.value = e.message }
  finally { actionLoading.value = false }
}

onMounted(load)
</script>
