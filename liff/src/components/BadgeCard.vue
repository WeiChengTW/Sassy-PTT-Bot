<template>
  <div
    class="rounded-2xl border p-4 flex items-center gap-4 transition-all duration-200
           hover:shadow-lift active:scale-[0.98] cursor-default select-none relative overflow-hidden"
    :class="rarityStyle.card"
  >
    <!-- Icon / Image -->
    <div
      class="shrink-0 w-14 h-14 rounded-2xl flex items-center justify-center text-3xl shadow-inner border border-white/40"
      :class="rarityStyle.icon"
    >
      <img
        v-if="badge.badge_image_url"
        :src="badge.badge_image_url"
        class="w-11 h-11 rounded-full object-cover shadow-sm"
      />
      <span v-else>{{ badge.badge_emoji }}</span>
    </div>

    <!-- Text -->
    <div class="flex-1 min-w-0">
      <p class="font-bold text-sm truncate" :class="rarityStyle.name">
        {{ badge.badge_name }}
      </p>
      <div class="flex items-center gap-2 mt-1">
        <span
          class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold shadow-2xs"
          :class="rarityStyle.pill"
        >
          {{ rarityLabel }}
        </span>
        <p v-if="displayDate" class="text-[11px] font-medium" :class="rarityStyle.date">
          🗓️ {{ displayDate }}
        </p>
      </div>
    </div>

    <!-- Rarity indicator -->
    <div class="w-2.5 h-2.5 rounded-full shrink-0" :class="rarityStyle.dot" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { rarityOf } from '@/constants/rarity'

const props = defineProps<{ badge: any }>()

const rarityStyle = computed(() => rarityOf(props.badge.badge_rarity))
const rarityLabel = computed(() => `${rarityStyle.value.zh}`)
const displayDate = computed(() => {
  const ts = props.badge.start_date || props.badge.earned_at
  if (!ts) return ''
  return new Date(ts * 1000).toLocaleDateString('zh-TW')
})
</script>
