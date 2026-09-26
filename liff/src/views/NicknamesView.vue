<template>
  <div class="space-y-6">
    <h1 class="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
      <span>🏷️ 本週稱號</span>
    </h1>

    <!-- 說明 -->
    <BaseCard class="p-4 card-rise">
      <p class="text-xs font-bold text-slate-700 mb-2">這是什麼？</p>
      <ul class="text-xs text-slate-500 leading-relaxed space-y-1 list-disc pl-4">
        <li>機器人每週日凌晨看一次大家最近的發言，幫每個人取一個暫時稱號。</li>
        <li>最近 7 天講超過 30 句就看 7 天；不夠就看 30 天；再不夠就跳過。</li>
        <li>每人最多留 {{ data?.max_per_member ?? 3 }} 個，新的進來就把最舊的擠掉。</li>
        <li>不會在群組公布，機器人聊天時會默默拿來叫你，而且比一般外號更常用。</li>
      </ul>
    </BaseCard>

    <div v-if="loading" class="space-y-4">
      <div class="skeleton h-28 rounded-2xl" />
      <div class="skeleton h-28 rounded-2xl" />
    </div>

    <EmptyState
      v-else-if="error"
      icon="⚠️"
      title="無法載入稱號"
      :description="error"
    />

    <EmptyState
      v-else-if="!data?.members.length"
      icon="🫥"
      title="還沒有稱號"
      description="機器人還沒幫大家取過稱號，等這週日凌晨再來看看。"
    />

    <div v-else>
      <SectionHeader title="成員稱號" icon="🏷️" :subtitle="`${data.members.length} 人`" />
      <div class="space-y-3">
        <BaseCard v-for="m in data.members" :key="m.name" class="p-4 card-rise">
          <div class="flex items-baseline gap-2 mb-3">
            <span class="text-sm font-bold text-slate-900">{{ m.name }}</span>
            <span v-if="m.aliases.length" class="text-[11px] text-slate-400 truncate">
              aka {{ m.aliases.slice(0, 3).join('、') }}
            </span>
          </div>
          <div class="divide-y divide-slate-100">
            <div v-for="(a, i) in m.auto_aliases" :key="a.name + a.created" class="py-2.5 first:pt-0 last:pb-0">
              <div class="flex items-center gap-2 mb-1">
                <span
                  class="text-xs font-bold px-2 py-0.5 rounded-full"
                  :class="i === 0 ? 'bg-brand-50 text-brand-600' : 'bg-slate-100 text-slate-500'"
                >
                  {{ a.name }}
                </span>
                <span v-if="i === 0" class="text-[10px] font-bold text-brand-500">最新</span>
                <span class="ml-auto text-[10px] text-slate-400 font-mono tabular-nums">
                  {{ a.created }} · 看 {{ a.window_days }} 天
                </span>
              </div>
              <p class="text-xs text-slate-500 leading-relaxed">{{ a.reason }}</p>
            </div>
          </div>
        </BaseCard>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, type NicknamesData } from '@/api/client'
import BaseCard from '@/components/BaseCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import SectionHeader from '@/components/SectionHeader.vue'

const data = ref<NicknamesData | null>(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try { data.value = await api.nicknames() }
  catch (e: any) { error.value = e?.message || '請求失敗'; console.error(e) }
  loading.value = false
})
</script>
