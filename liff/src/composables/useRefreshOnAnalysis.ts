import { watch } from 'vue'
import { useAnalysisStore } from '@/stores/analysis'

/**
 * 註冊一個 callback：當全域 LLM 分析版本變動時自動呼叫。
 *
 * 用途：管理員在話題頁按 🔄 後，即使使用者目前停留在其他頁面，
 * 切換過去時 watcher 不會自動觸發（因為元件還在快取），
 * 但下次重新掛載時 onMounted → loadXxx 會撈到最新資料。
 *
 * 對於「當前已掛載」的頁面（Dashboard / Profile / Pulse / 等等），
 * 則會立刻背景重抓，UI 不閃 skeleton。
 *
 * @example
 *   async function loadDashboard() { ... }
 *   onMounted(loadDashboard)
 *   useRefreshOnAnalysis(loadDashboard)
 */
export function useRefreshOnAnalysis(refetch: () => void | Promise<void>) {
  const store = useAnalysisStore()
  watch(() => store.version, () => { refetch() })
}
