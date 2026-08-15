<template>
  <div
    class="rounded-2xl border p-4 flex items-center gap-4 transition-transform duration-150
           active:scale-[0.97] cursor-default select-none"
    :class="rarityStyle.card"
  >
    <!-- Icon / Image -->
    <div class="flex-shrink-0 w-14 h-14 rounded-2xl flex items-center justify-center text-3xl"
         :class="rarityStyle.icon">
      <img v-if="badge.badge_image_url"
           :src="badge.badge_image_url"
           class="w-10 h-10 rounded-full object-cover" />
      <span v-else>{{ badge.badge_emoji }}</span>
    </div>

    <!-- Text -->
    <div class="flex-1 min-w-0">
      <p class="font-semibold text-sm truncate" :class="rarityStyle.name">
        {{ badge.badge_name }}
      </p>
      <span class="inline-flex items-center gap-1 mt-0.5 px-2 py-0.5 rounded-full text-[11px]
                   font-medium" :class="rarityStyle.pill">
        {{ rarityLabel }}
      </span>
      <p v-if="earnedDate" class="text-xs mt-1" :class="rarityStyle.date">
        {{ earnedDate }}
      </p>
    </div>

    <!-- Rarity glow dot -->
    <div class="w-2 h-2 rounded-full flex-shrink-0" :class="rarityStyle.dot" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { rarityOf } from '@/constants/rarity'

const props = defineProps<{ badge: any }>()

const rarityStyle = computed(() => rarityOf(props.badge.badge_rarity))
const rarityLabel = computed(() => `${rarityStyle.value.emoji} ${rarityStyle.value.zh}`)
const earnedDate = computed(() => {
  if (!props.badge.earned_at) return ''
  return new Date(props.badge.earned_at * 1000).toLocaleDateString('zh-TW')
})
</script>
