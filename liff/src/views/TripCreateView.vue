<template>
  <div class="space-y-6">
    <button
      @click="$router.back()"
      class="text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors inline-flex items-center gap-1 btn-press px-2.5 py-1.5 rounded-xl bg-white border border-slate-200"
    >
      <span>← 返回</span>
    </button>

    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
        <span>🆕 建立旅行與事件</span>
      </h1>
    </div>

    <BaseCard class="p-5 card-rise">
      <form @submit.prevent="submit" class="space-y-5">
        <!-- 類型切換：單日事件 vs 多日旅行 -->
        <div>
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">活動形式</label>
          <div class="grid grid-cols-2 gap-2 bg-slate-100 p-1 rounded-xl border border-slate-200/80">
            <button
              type="button"
              @click="mode = 'event'"
              class="py-2.5 text-xs rounded-lg font-bold transition-all flex items-center justify-center gap-1.5 btn-press"
              :class="mode === 'event' ? 'bg-white text-brand-600 shadow-sm' : 'text-slate-500 hover:text-slate-800'"
            >
              <span>⚡</span> 單日事件（當天）
            </button>
            <button
              type="button"
              @click="mode = 'trip'"
              class="py-2.5 text-xs rounded-lg font-bold transition-all flex items-center justify-center gap-1.5 btn-press"
              :class="mode === 'trip' ? 'bg-white text-brand-600 shadow-sm' : 'text-slate-500 hover:text-slate-800'"
            >
              <span>🧳</span> 多日旅行（跨日）
            </button>
          </div>
        </div>

        <!-- 標題與自訂 Emoji -->
        <div class="flex gap-3 items-start">
          <div class="w-18 shrink-0">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Emoji</label>
            <input
              v-model="form.custom_emoji"
              class="w-full bg-slate-50 border border-slate-200 rounded-xl px-2 py-2.5 text-center text-xl focus:outline-none focus:ring-2 focus:ring-brand-400 focus:bg-white transition-all"
              placeholder="🎒"
            />
          </div>
          <div class="flex-1 min-w-0">
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">名稱 / 標題 *</label>
            <input
              v-model="form.title"
              required
              class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand-400 focus:bg-white transition-all"
              :placeholder="mode === 'event' ? '例如：聚餐吃火鍋、夜唱' : '例如：花東三日遊、宜蘭包棟'"
            />
          </div>
        </div>

        <div>
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">活動地點 *</label>
          <input
            v-model="form.location"
            required
            class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand-400 focus:bg-white transition-all"
            placeholder="例如：墾丁、內湖高中、宜蘭礁溪"
          />
        </div>

        <!-- 日期選擇 -->
        <div v-if="mode === 'event'">
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">發生日期 *</label>
          <input
            v-model="form.startDate"
            type="date"
            required
            class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand-400 focus:bg-white transition-all"
          />
        </div>
        <div v-else class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">開始日期 *</label>
            <input
              v-model="form.startDate"
              type="date"
              required
              class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand-400 focus:bg-white transition-all"
            />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">結束日期 *</label>
            <input
              v-model="form.endDate"
              type="date"
              required
              :min="form.startDate"
              class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand-400 focus:bg-white transition-all"
            />
          </div>
        </div>

        <!-- 類型標籤 -->
        <div>
          <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">類型標籤（可複選）</label>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="t in TRIP_TYPES"
              :key="t.value"
              type="button"
              @click="toggleType(t.value)"
              class="rounded-full px-3 py-1.5 text-xs font-semibold border transition-all duration-150 btn-press"
              :class="form.types.includes(t.value)
                ? 'bg-brand-600 text-white border-brand-600 shadow-sm'
                : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'"
            >
              {{ t.emoji }} {{ t.label }}
            </button>
          </div>
        </div>

        <div class="flex gap-3 pt-3 border-t border-slate-100">
          <button
            type="submit"
            :disabled="loading"
            class="flex-1 bg-brand-600 hover:bg-brand-700 text-white rounded-xl py-3 text-sm font-bold shadow-md shadow-brand-500/20 disabled:opacity-50 transition-all btn-press"
          >
            {{ loading ? '建立中...' : (mode === 'event' ? '建立事件' : '建立旅行') }}
          </button>
          <button
            type="button"
            @click="$router.back()"
            class="px-5 border border-slate-200 rounded-xl py-3 text-sm font-semibold text-slate-600 hover:bg-slate-50 transition-all btn-press"
          >
            取消
          </button>
        </div>
        <p v-if="error" class="text-danger-600 text-xs font-semibold text-center mt-2">{{ error }}</p>
      </form>
    </BaseCard>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import { TRIP_TYPES } from '@/constants/tripTypes'
import BaseCard from '@/components/BaseCard.vue'

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
