<template>
  <div>
    <!-- 標題 -->
    <div class="flex items-baseline gap-2 mb-1">
      <h2 class="font-semibold text-sm text-gray-700">{{ board.emoji }} {{ board.title }}</h2>
      <span v-if="board.sparse"
            class="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-200">
        資料量少 · 僅供參考
      </span>
    </div>
    <p class="text-xs text-gray-400 mb-2">{{ board.subtitle }}</p>

    <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
      <!-- 雷達圖（全能王） -->
      <div v-if="board.variant === 'radar'" class="p-4">
        <div v-if="radarData" class="max-w-xs mx-auto">
          <Radar :data="radarData" :options="radarOptions" />
        </div>
        <div v-else class="py-4 text-sm text-gray-400 text-center">尚無足夠資料</div>
      </div>

      <!-- 排名列（rank / score） -->
      <div v-else class="divide-y">
        <div v-for="(u, i) in board.rows" :key="u.user_id"
             class="flex items-center px-4 py-3 gap-3"
             :class="i === 0 ? 'bg-amber-50/60' : i === 1 ? 'bg-slate-50/60' : ''">
          <span class="w-6 text-center shrink-0"
                :class="i < 3 ? 'text-base' : 'text-sm text-gray-300 tabular-nums font-medium'">
            {{ medal(i) }}
          </span>
          <div class="flex-1 min-w-0">
            <p class="text-sm text-gray-800 truncate">{{ u.name || u.user_id }}</p>
            <p v-if="u.detail" class="text-xs text-gray-400 truncate">{{ u.detail }}</p>
            <!-- score variant: 子分數 pills -->
            <div v-if="u.breakdown" class="flex flex-wrap gap-1 mt-1">
              <span v-for="(v, k) in u.breakdown" :key="k"
                    class="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
                {{ k }} {{ v }}
              </span>
            </div>
          </div>
          <span class="text-sm font-semibold tabular-nums shrink-0"
                :style="{ color: board.accent || '#4f46e5' }">
            {{ u.value_str }}
          </span>
        </div>
        <div v-if="!board.rows.length" class="px-4 py-4 text-sm text-gray-400 text-center">
          尚無{{ board.title }}資料
        </div>

        <!-- highlight callout -->
        <div v-if="board.highlight"
             class="px-4 py-3 bg-gray-50/80 border-t border-dashed border-gray-200">
          <p class="text-[11px] text-gray-400 mb-0.5">{{ board.highlight.label }}</p>
          <p class="text-sm text-gray-700">
            <span class="font-medium">{{ board.highlight.name }}</span>
            <span class="ml-2 font-semibold" :style="{ color: board.accent || '#4f46e5' }">
              {{ board.highlight.value_str }}
            </span>
          </p>
          <p v-if="board.highlight.note" class="text-xs text-gray-400 mt-0.5 truncate">
            {{ board.highlight.note }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Radar } from 'vue-chartjs'
import {
  Chart as ChartJS, RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend,
} from 'chart.js'
import type { Board } from '@/api/client'

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
  scales: { r: { min: 0, max: 100, ticks: { display: false }, pointLabels: { font: { size: 11 } } } },
  plugins: { legend: { position: 'bottom' as const, labels: { font: { size: 11 }, boxWidth: 12 } } },
}
</script>
