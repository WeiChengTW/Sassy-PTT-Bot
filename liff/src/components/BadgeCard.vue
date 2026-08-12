<template>
  <div class="bg-white rounded-xl shadow p-4 flex items-center gap-3">
    <div class="text-4xl">{{ badge.badge_image_url ? '' : badge.badge_emoji }}</div>
    <img v-if="badge.badge_image_url" :src="badge.badge_image_url" class="w-12 h-12 rounded-full object-cover" />
    <div>
      <p class="font-semibold text-sm">{{ badge.badge_name }}</p>
      <p class="text-xs text-gray-400">{{ rarityLabel }}</p>
      <p class="text-xs text-gray-400">{{ earnedDate }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ badge: any }>()

const RARITY_LABEL: Record<string, string> = {
  common: '🟢 一般', rare: '🔵 稀有', epic: '🟣 史詩', legendary: '🟡 傳說',
}

const rarityLabel = computed(() => RARITY_LABEL[props.badge.badge_rarity] || props.badge.badge_rarity)
const earnedDate = computed(() => {
  if (!props.badge.earned_at) return ''
  return new Date(props.badge.earned_at * 1000).toLocaleDateString('zh-TW')
})
</script>