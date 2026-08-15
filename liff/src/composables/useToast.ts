// 全域單例 toast 狀態。於 App.vue 掛一個 <Toast>，各處呼叫 toast.success()/error()。
import { reactive, readonly } from 'vue'

export type ToastType = 'success' | 'error'

interface ToastState {
  visible: boolean
  message: string
  type: ToastType
}

const state = reactive<ToastState>({
  visible: false,
  message: '',
  type: 'success',
})

let timer: ReturnType<typeof setTimeout> | null = null

function show(message: string, type: ToastType, duration = 2600) {
  if (timer) clearTimeout(timer)
  state.message = message
  state.type = type
  state.visible = true
  timer = setTimeout(() => { state.visible = false }, duration)
}

export function useToast() {
  return {
    state: readonly(state),
    success: (msg: string) => show(msg, 'success'),
    error: (msg: string) => show(msg, 'error'),
  }
}
