<template>
  <div>
    <button @click="$router.back()" class="text-sm text-gray-500 mb-4">← 返回</button>
    <h1 class="text-xl font-bold mb-4">🆕 建立旅行 / 事件</h1>
    <form @submit.prevent="submit" class="space-y-4">
      <!-- 類型切換：單日事件 vs 多日旅行 -->
      <div>
        <label class="block text-sm font-medium mb-1.5 text-gray-700">形式</label>
        <div class="grid grid-cols-2 gap-2 bg-gray-100 p-1 rounded-xl border border-gray-200">
          <button type="button" @click="mode = 'event'"
                  class="py-2 text-xs rounded-lg font-medium transition-all flex items-center justify-center gap-1.5"
                  :class="mode === 'event' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-800'">
            <span>⚡</span> 單日事件（當天）
          </button>
          <button type="button" @click="mode = 'trip'"
                  class="py-2 text-xs rounded-lg font-medium transition-all flex items-center justify-center gap-1.5"
                  :class="mode === 'trip' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-800'">
            <span>🧳</span> 多日旅行（有起訖日）
          </button>
        </div>
      </div>

      <!-- 標題與自訂 Emoji -->
      <div class="flex gap-2 items-start">
        <div class="w-16 shrink-0">
          <label class="block text-sm font-medium mb-1">Emoji</label>
          <input v-model="form.custom_emoji"
                 class="w-full border rounded-lg px-2 py-2 text-center text-base focus:outline-none focus:border-blue-500"
                 placeholder="🎒" />
        </div>
        <div class="flex-1 min-w-0">
          <label class="block text-sm font-medium mb-1">名稱 / 標題 *</label>
          <input v-model="form.title" required
                 class="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                 :placeholder="mode === 'event' ? '例如：水晶小火鍋、烤肉' : '例如：墾丁三日遊、宜蘭跨年'" />
        </div>
      </div>

      <div>
        <label class="block text-sm font-medium mb-1">地點 *</label>
        <input v-model="form.location" required
               class="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
               placeholder="例如：墾丁、內湖高中、宜蘭" />
      </div>

      <!-- 日期選擇 -->
      <div v-if="mode === 'event'">
        <label class="block text-sm font-medium mb-1">發生日期 *</label>
        <input v-model="form.startDate" type="date" required
               class="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
      </div>
      <div v-else class="grid grid-cols-2 gap-2">
        <div>
          <label class="block text-sm font-medium mb-1">開始日期 *</label>
          <input v-model="form.startDate" type="date" required
                 class="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
        </div>
        <div>
          <label class="block text-sm font-medium mb-1">結束日期 *</label>
          <input v-model="form.endDate" type="date" required
                 :min="form.startDate"
                 class="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
        </div>
      </div>

      <!-- 類型標籤 -->
      <div>
        <label class="block text-sm font-medium mb-1">類型標籤（可複選）</label>
        <div class="flex flex-wrap gap-2">
          <button v-for="t in TRIP_TYPES" :key="t.value" type="button"
                  @click="toggleType(t.value)"
                  class="rounded-full px-3 py-1.5 text-xs border transition-colors"
                  :class="form.types.includes(t.value)
                    ? 'bg-blue-600 text-white border-blue-600 font-medium'
                    : 'bg-gray-100 text-gray-600 border-gray-200'">
            {{ t.emoji }} {{ t.label }}
          </button>
        </div>
      </div>

      <div class="flex gap-2 pt-2">
        <button type="submit" :disabled="loading"
                class="flex-1 bg-blue-600 text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-50 hover:bg-blue-700 transition-colors">
          {{ loading ? '建立中...' : (mode === 'event' ? '建立事件' : '建立旅行') }}
        </button>
        <button type="button" @click="$router.back()"
                class="px-4 border rounded-lg py-2.5 text-sm text-gray-600">取消</button>
      </div>
      <p v-if="error" class="text-red-500 text-sm">{{ error }}</p>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import { TRIP_TYPES } from '@/constants/tripTypes'

const router = useRouter()
const loading = ref(false)
const error = ref('')
const mode = ref<'event' | 'trip'>('event')
const form = ref({
  title: '',
  location: '',
  startDate: '',
  endDate: '',
  custom_emoji: '',
  types: [] as string[],
})

function toggleType(value: string) {
  const i = form.value.types.indexOf(value)
  if (i >= 0) form.value.types.splice(i, 1)
  else form.value.types.push(value)
}

async function submit() {
  loading.value = true
  error.value = ''
  try {
    const startDate = Math.floor(new Date(form.value.startDate).getTime() / 1000)
    let endDate: number | undefined = undefined
    if (mode.value === 'trip' && form.value.endDate) {
      endDate = Math.floor(new Date(form.value.endDate).getTime() / 1000)
    }
    const res = await api.adminCreateTrip({
      title: form.value.title.trim(),
      location: form.value.location.trim(),
      start_date: startDate,
      end_date: endDate,
      types: form.value.types,
      custom_emoji: form.value.custom_emoji.trim() || undefined,
    })
    router.push(`/admin/trips/${res.trip_id}`)
  } catch (e: any) {
    error.value = e.message || '建立失敗'
  } finally {
    loading.value = false
  }
}
</script>
