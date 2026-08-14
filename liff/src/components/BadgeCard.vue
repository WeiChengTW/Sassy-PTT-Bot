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

const props = defineProps<{ badge: any }>()

type Rarity = 'common' | 'rare' | 'epic' | 'legendary'

const RARITY_STYLES: Record<Rarity, {
  card: string; icon: string; name: string; pill: string; date: string; dot: string
}> = {
  common: {
    card: 'bg-white border-gray-200',
    icon: 'bg-gray-100',
    name: 'text-gray-800',
    pill: 'bg-gray-100 text-gray-500',
    date: 'text-gray-400',
    dot: 'bg-gray-300',
  },
  rare: {
    card: 'bg-blue-50 border-blue-200',
    icon: 'bg-blue-100',
    name: 'text-blue-900',
    pill: 'bg-blue-100 text-blue-600',
    date: 'text-blue-400',
    dot: 'bg-blue-400',
  },
  epic: {
    card: 'bg-purple-50 border-purple-300',
    icon: 'bg-purple-100',
    name: 'text-purple-900',
    pill: 'bg-purple-100 text-purple-600',
    date: 'text-purple-400',
    dot: 'bg-purple-500',
  },
  legendary: {
    card: 'bg-amber-50 border-amber-300 badge-legendary',
    icon: 'bg-amber-100',
    name: 'text-amber-900',
    pill: 'bg-amber-100 text-amber-600',
    date: 'text-amber-400',
    dot: 'bg-amber-400',
  },
}

const RARITY_LABEL: Record<Rarity, string> = {
  common: '一般',
  rare: '✦ 稀有',
  epic: '✦✦ 史詩',
  legendary: '★ 傳說',
}

const rarity = computed<Rarity>(() => {
  const r = props.badge.badge_rarity as Rarity
  return RARITY_STYLES[r] ? r : 'common'
})

const rarityStyle = computed(() => RARITY_STYLES[rarity.value])
const rarityLabel = computed(() => RARITY_LABEL[rarity.value])
const earnedDate = computed(() => {
  if (!props.badge.earned_at) return ''
  return new Date(props.badge.earned_at * 1000).toLocaleDateString('zh-TW')
})
</script>
