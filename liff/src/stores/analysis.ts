import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 全域 LLM 分析版本計數器。
 *
 * 任何頁面只要資料依賴 messages.analyzed_at 相關欄位
 * （topics / keywords / sentiment / locations / summary），
 * 都應該用 useRefreshOnAnalysis() 訂閱這個 store 的 version，
 * 確保管理員在話題頁按 🔄 後切換到該頁時能拿到新資料。
 */
export const useAnalysisStore = defineStore('analysis', () => {
  const version = ref(0)
  const lastBumpedAt = ref(0)

  function bumped(updated: number = 0, when: number = Date.now()) {
    version.value++
    if (updated > 0) lastBumpedAt.value = Math.floor(when / 1000)
  }

  return { version, lastBumpedAt, bumped }
})
