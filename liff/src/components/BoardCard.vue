<template>
  <div class="space-y-3">
    <!-- 標題 -->
    <div class="flex items-baseline gap-2 px-1">
      <h2 class="font-bold text-sm text-slate-800 flex items-center gap-1.5">
        <span>{{ board.emoji }}</span>
        <span>{{ board.title }}</span>
      </h2>
      <span
        v-if="board.sparse"
        class="text-[10px] px-2 py-0.5 rounded-full bg-accent-50 text-accent-700 border border-accent-200 font-medium"
      >
        資料量少 · 僅供參考
      </span>
    </div>
    <p class="text-xs text-slate-400 -mt-1 px-1 font-medium">{{ board.subtitle }}</p>

    <BaseCard class="overflow-hidden card-rise">
      <!-- 雷達圖（全能王） -->
      <div v-if="board.variant === 'radar'" class="p-4">
        <div v-if="radarData" class="max-w-xs mx-auto">
          <Radar :data="radarData" :options="radarOptions" />
        </div>
        <div v-else class="py-6 text-xs text-slate-400 text-center">尚無足夠資料</div>
      </div>

      <!-- 排名列（rank / score） -->
      <div v-else class="divide-y divide-slate-100">
        <div
          v-for="(u, i) in board.rows"
          :key="u.user_id"
          class="flex items-center px-4 py-3 gap-3 transition-colors hover:bg-slate-50/80"
          :class="i === 0 ? 'bg-accent-50/40' : i === 1 ? 'bg-slate-50/60' : ''"
        >
          <span
            class="w-6 text-center shrink-0 font-bold tabular-nums"
            :class="i === 0 ? 'text-accent-600' : i === 1 ? 'text-slate-400' : i === 2 ? 'text-amber-700' : 'text-slate-300 font-normal text-xs'"
          >
            {{ medal(i) }}
          </span>
          <div class="flex-1 min-w-0">
            <p class="text-xs font-bold truncate text-slate-800">{{ u.name || u.user_id }}</p>
            <p v-if="u.detail" class="text-[11px] text-slate-400 truncate">{{ u.detail }}</p>
            <!-- score variant: 子分數 pills -->
            <div v-if="u.breakdown" class="flex flex-wrap gap-1 mt-1">
              <span
                v-for="(v, k) in u.breakdown"
                :key="k"
                class="text-[10px] px-1.5 py-0.2 rounded-md bg-slate-100 text-slate-600 font-medium font-mono"
              >
                {{ k }} {{ v }}
              </span>
            </div>
          </div>
          <span
            class="text-xs font-bold font-mono tabular-nums shrink-0"
            :style="{ color: board.accent || '#6366f1' }"
          >
            {{ u.value_str }}
          </span>
        </div>
        <div v-if="!board.rows.length" class="px-4 py-6 text-xs text-slate-400 text-center">
          尚無 {{ board.title }} 資料
        </div>

        <!-- highlight callout -->
        <div
          v-if="board.highlight"
          class="px-4 py-3 bg-brand-50/40 border-t border-dashed border-brand-100"
        >
          <p class="text-[10px] font-bold text-brand-600 uppercase tracking-wider mb-0.5">{{ board.highlight.label }}</p>
          <p class="text-xs text-slate-700 flex items-center justify-between">
            <span class="font-bold">{{ board.highlight.name }}</span>
            <span class="font-black font-mono" :style="{ color: board.accent || '#6366f1' }">
              {{ board.highlight.value_str }}
            </span>
          </p>
          <p v-if="board.highlight.note" class="text-[11px] text-slate-400 mt-0.5 truncate">
            {{ board.highlight.note }}
          </p>
        </div>
      </div>
    </BaseCard>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Radar } from 'vue-chartjs'
import {
  Chart as ChartJS, RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend,
} from 'chart.js'
import type { Board } from '@/api/client'
import BaseCard from '@/components/BaseCard.vue'

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend)

const props = defineProps<{ board: Board }>()

function medal(i: number): string {
  return ['🥇', '🥈', '🥉'][i] || String(i + 1)
}

const RADAR_COLORS = ['#f59e0b', '#6366f1', '#10b981']

const radarData = computed(() => {
  const top = props.board.rows.filter(r => r.axes).slice(0, 3)
  if (!top.length) return null
  const labels = Object.keys(top[0].axes || {})
  return {
    labels,
    datasets: top.map((u, i) => ({
      label: u.name || u.user_id,
      data: labels.map(l => (u.axes || {})[l] ?? 0),
      backgroundColor: RADAR_COLORS[i] + '33',
      borderColor: RADAR_COLORS[i],
      borderWidth: 2,
      pointBackgroundColor: RADAR_COLORS[i],
    })),
  }
})

const radarOptions = {
  responsive: true,
  scales: {
    r: {
      min: 0,
      max: 100,
      ticks: { display: false },
      pointLabels: { font: { size: 10, family: 'Inter, Noto Sans TC', weight: 'bold' as const }, color: '#64748b' },
    },
  },
  plugins: {
    legend: {
      position: 'bottom' as const,
      labels: { font: { size: 10, family: 'Inter, Noto Sans TC' }, boxWidth: 10, padding: 8 },
    },
  },
}
</script>
