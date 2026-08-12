<template>
  <div>
    <h1 class="text-xl font-bold mb-4">🤝 互動關係</h1>
    <div v-if="loading" class="text-center py-8 text-gray-400">載入中...</div>
    <div v-else-if="data">
      <!-- 最佳拍檔 -->
      <h2 class="font-semibold mb-2">💬 最佳拍檔（依回覆次數）</h2>
      <div class="bg-white rounded-xl shadow divide-y mb-6">
        <div v-if="!data.best_pairs.length" class="px-4 py-3 text-sm text-gray-400">
          尚無回覆互動資料
        </div>
        <div v-for="(pair, i) in data.best_pairs" :key="i"
             class="flex items-center px-4 py-3 gap-2">
          <span class="text-gray-400 text-sm w-5">{{ i + 1 }}</span>
          <span class="flex-1 text-sm font-medium">
            {{ pair.user1_name || pair.user1_id }}
            <span class="text-gray-400 mx-1">↔</span>
            {{ pair.user2_name || pair.user2_id }}
          </span>
          <span class="text-sm text-gray-500">{{ pair.count }} 次</span>
        </div>
      </div>

      <!-- 社交網絡圖 -->
      <h2 class="font-semibold mb-2">🕸️ 互動網絡</h2>
      <div class="bg-white rounded-xl shadow p-2 mb-6">
        <svg ref="svgRef" :width="svgW" :height="svgH" class="w-full" />
        <p v-if="!data.network_edges.length" class="text-center text-sm text-gray-400 py-4">
          尚無互動資料
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { api } from '@/api/client'

const data = ref<any>(null)
const loading = ref(true)
const svgRef = ref<SVGSVGElement | null>(null)
const simRef = ref<any>(null)
const svgW = 340
const svgH = 280

async function drawGraph() {
  if (!svgRef.value || !data.value?.network_edges.length) return
  // Dynamic import D3 so it's code-split
  const d3 = await import('d3')

  const nodes: any[] = data.value.network_nodes.map((n: any) => ({ ...n }))
  const links: any[] = data.value.network_edges.map((e: any) => ({
    source: e.source, target: e.target, weight: e.weight,
  }))

  const svg = d3.select(svgRef.value)
  svg.selectAll('*').remove()

  const maxMsg = Math.max(...nodes.map((n: any) => n.message_count), 1)
  const rScale = d3.scaleSqrt().domain([0, maxMsg]).range([6, 20])
  const maxW = Math.max(...links.map((l: any) => l.weight), 1)
  const strokeScale = d3.scaleLinear().domain([0, maxW]).range([1, 5])

  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id((d: any) => d.id).distance(80))
    .force('charge', d3.forceManyBody().strength(-120))
    .force('center', d3.forceCenter(svgW / 2, svgH / 2))
    .force('collision', d3.forceCollide().radius((d: any) => rScale(d.message_count) + 4))
  simRef.value = sim

  const link = svg.append('g')
    .selectAll('line')
    .data(links)
    .join('line')
    .attr('stroke', '#cbd5e1')
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
    .attr('fill', '#60a5fa')
    .attr('stroke', '#fff')
    .attr('stroke-width', 2)

  node.append('text')
    .text((d: any) => (d.name || d.id).slice(0, 4))
    .attr('text-anchor', 'middle')
    .attr('dy', '0.35em')
    .attr('font-size', 9)
    .attr('fill', '#fff')
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

onMounted(async () => {
  try { data.value = await api.interactions() }
  catch (e) { console.error(e) }
  finally {
    loading.value = false
    await nextTick()
    drawGraph()
  }
})
</script>
