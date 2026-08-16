<template>
  <div class="space-y-6">
    <h1 class="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
      <span>🤝 群組互動關係網絡</span>
    </h1>

    <div v-if="loading" class="space-y-4">
      <div class="skeleton h-32 rounded-2xl" />
      <div class="skeleton h-64 rounded-2xl" />
    </div>

    <EmptyState
      v-else-if="error"
      icon="⚠️"
      title="無法載入互動資料"
      :description="error"
    />

    <div v-else-if="data" class="space-y-6">
      <!-- 最佳拍檔 -->
      <div>
        <SectionHeader title="群組最佳拍檔" icon="🏆" subtitle="依雙向回覆次數" />
        <BaseCard class="overflow-hidden card-rise">
          <div v-if="!data.best_pairs.length" class="px-4 py-8 text-sm text-slate-400 text-center">
            尚無回覆互動資料
          </div>
          <div v-else class="divide-y divide-slate-100">
            <div
              v-for="(pair, i) in data.best_pairs"
              :key="i"
              class="flex items-center px-4 py-3.5 gap-2 transition-colors hover:bg-slate-50/80"
              :class="i === 0 ? 'bg-accent-50/40' : ''"
            >
              <span
                class="text-xs w-6 text-center font-bold tabular-nums"
                :class="i === 0 ? 'text-accent-600' : 'text-slate-400'"
              >
                {{ i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1 }}
              </span>
              <span class="flex-1 text-xs font-bold text-slate-800 truncate">
                {{ pair.user1_name || pair.user1_id }}
                <span class="text-slate-300 mx-1 font-normal">↔</span>
                {{ pair.user2_name || pair.user2_id }}
              </span>
              <span class="text-xs font-bold font-mono tabular-nums text-brand-600 bg-brand-50 px-2 py-0.5 rounded-full">
                {{ pair.count }} 次回覆
              </span>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- 社交網絡圖 -->
      <div>
        <SectionHeader title="社交引力網絡圖" icon="🕸️" />
        <BaseCard class="p-4 card-rise flex flex-col items-center min-h-[300px] justify-center">
          <svg
            v-show="data.network_edges && data.network_edges.length"
            ref="svgRef"
            :width="svgW"
            :height="svgH"
            class="w-full max-w-[340px]"
          />
          <p v-if="!data.network_edges || !data.network_edges.length" class="text-center text-xs text-slate-400 py-6">
            互動數據尚不足以繪製網絡圖
          </p>
        </BaseCard>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import * as d3 from 'd3'
import { api } from '@/api/client'
import { useRefreshOnAnalysis } from '@/composables/useRefreshOnAnalysis'
import BaseCard from '@/components/BaseCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import SectionHeader from '@/components/SectionHeader.vue'

const data = ref<any>(null)
const loading = ref(true)
const error = ref('')
const svgRef = ref<SVGSVGElement | null>(null)
const simRef = ref<any>(null)
const svgW = 340
const svgH = 280

function drawGraph() {
  if (!svgRef.value || !data.value?.network_edges?.length) return

  const nodes: any[] = (data.value.network_nodes || []).map((n: any) => ({ ...n }))
  const links: any[] = (data.value.network_edges || []).map((e: any) => ({
    source: e.source, target: e.target, weight: e.weight,
  }))

  const svg = d3.select(svgRef.value)
  svg.selectAll('*').remove()

  const maxMsg = Math.max(...nodes.map((n: any) => n.message_count), 1)
  const rScale = d3.scaleSqrt().domain([0, maxMsg]).range([10, 24])
  const maxW = Math.max(...links.map((l: any) => l.weight), 1)
  const strokeScale = d3.scaleLinear().domain([0, maxW]).range([1.5, 6])

  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id((d: any) => d.id).distance(80))
    .force('charge', d3.forceManyBody().strength(-120))
    .force('center', d3.forceCenter(svgW / 2, svgH / 2))
    .force('collision', d3.forceCollide().radius((d: any) => rScale(d.message_count) + 5))
  simRef.value = sim

  const link = svg.append('g')
    .selectAll('line')
    .data(links)
    .join('line')
    .attr('stroke', '#cbd5e1')
    .attr('stroke-opacity', 0.7)
    .attr('stroke-width', (d: any) => strokeScale(d.weight))

  const node = svg.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .call(d3.drag<any, any>()
      .on('start', (event, d) => {
        if (!event.active) sim.alphaTarget(0.3).restart()
        d.fx = d.x; d.fy = d.y
      })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
      .on('end', (event, d) => {
        if (!event.active) sim.alphaTarget(0)
        d.fx = null; d.fy = null
      }))

  node.append('circle')
    .attr('r', (d: any) => rScale(d.message_count))
    .attr('fill', '#6366f1')
    .attr('stroke', '#ffffff')
    .attr('stroke-width', 2.5)
    .attr('class', 'shadow-md cursor-grab active:cursor-grabbing')

  node.append('text')
    .text((d: any) => (d.name || d.id).slice(0, 4))
    .attr('text-anchor', 'middle')
    .attr('dy', '0.35em')
    .attr('font-size', 10)
    .attr('font-family', 'Inter, Noto Sans TC, sans-serif')
    .attr('font-weight', '700')
    .attr('fill', '#ffffff')
    .attr('pointer-events', 'none')

  sim.on('tick', () => {
    link
      .attr('x1', (d: any) => d.source.x)
      .attr('y1', (d: any) => d.source.y)
      .attr('x2', (d: any) => d.target.x)
      .attr('y2', (d: any) => d.target.y)
    node.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
  })
}

onUnmounted(() => {
  if (simRef.value) simRef.value.stop()
})

async function loadInteractions() {
  try {
    loading.value = true
    data.value = await api.interactions()
  } catch (e: any) {
    error.value = e?.message || '請求失敗'
    console.error(e)
  } finally {
    loading.value = false
    await nextTick()
    setTimeout(() => {
      drawGraph()
    }, 50)
  }
}

onMounted(async () => {
  await loadInteractions()
})

watch(() => data.value, () => {
  nextTick(() => drawGraph())
})

useRefreshOnAnalysis(loadInteractions)
</script>
