<template>
  <div>
    <button @click="$router.back()" class="text-sm text-gray-500 mb-4">← 返回</button>
    <h1 class="text-xl font-bold mb-4">🆕 建立旅行</h1>
    <form @submit.prevent="submit" class="space-y-4">
      <div>
        <label class="block text-sm font-medium mb-1">標題 *</label>
        <input v-model="form.title" required
               class="w-full border rounded-lg px-3 py-2 text-sm" placeholder="墾丁三日遊" />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">地點 *</label>
        <input v-model="form.location" required
               class="w-full border rounded-lg px-3 py-2 text-sm" placeholder="墾丁" />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">出發日 *</label>
        <input v-model="form.startDate" type="date" required
               class="w-full border rounded-lg px-3 py-2 text-sm" />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">類型</label>
        <select v-model="form.tripType" class="w-full border rounded-lg px-3 py-2 text-sm">
          <option value="">請選擇</option>
          <option value="beach">海灘</option>
          <option value="mountain">山岳</option>
          <option value="city">城市</option>
          <option value="other">其他</option>
        </select>
      </div>
      <div class="flex gap-2 pt-2">
        <button type="submit" :disabled="loading"
                class="flex-1 bg-blue-600 text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50">
          {{ loading ? '建立中...' : '建立旅行' }}
        </button>
        <button type="button" @click="$router.back()"
                class="flex-1 border rounded-lg py-2 text-sm">取消</button>
      </div>
      <p v-if="error" class="text-red-500 text-sm">{{ error }}</p>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'

const router = useRouter()
const loading = ref(false)
const error = ref('')
const form = ref({ title: '', location: '', startDate: '', tripType: '' })

async function submit() {
  loading.value = true
  error.value = ''
  try {
    const startDate = Math.floor(new Date(form.value.startDate).getTime() / 1000)
    const res = await api.adminCreateTrip({
      title: form.value.title,
      location: form.value.location,
      start_date: startDate,
      type: form.value.tripType || null,
    })
    router.push(`/admin/trips/${res.trip_id}`)
  } catch (e: any) {
    error.value = e.message || '建立失敗'
  } finally {
    loading.value = false
  }
}
</script>
