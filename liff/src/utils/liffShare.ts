// 智慧發送路由：以使用者本人名義把 Flex 小卡送出，完全不消耗官方帳號 Push 額度。
// SDK 已於 stores/auth.ts 的 init() 完成 liff.init，此處直接使用全域單例。
import liff from '@line/liff'
import type { FlexMessage } from './flexTripCard'

export type ShareMode = 'direct' | 'picker'

export interface ShareResult {
  success: boolean
  mode: ShareMode
}

/**
 * 依開啟情境分流：
 *  - 群組 / 多人聊天室（context.type group|room）：liff.sendMessages 直發後關窗。
 *  - 其他（1:1 / 外部）：喚起 shareTargetPicker 讓使用者挑選目標。
 *  - 皆不支援：拋錯，由呼叫端顯示友善提示。
 * picker 被使用者取消時回傳 { success:false, mode:'picker' }。
 */
export async function shareFlexMessage(message: FlexMessage): Promise<ShareResult> {
  if (!liff.isLoggedIn()) {
    liff.login()
    return { success: false, mode: 'direct' }
  }

  const ctx = liff.getContext()

  // 1. 群組環境：以個人名義直接送出
  if (ctx && (ctx.type === 'group' || ctx.type === 'room')) {
    await liff.sendMessages([message as any])
    liff.closeWindow()
    return { success: true, mode: 'direct' }
  }

  // 2. 外部 / 個人環境：呼叫分享目標選擇器
  if (liff.isApiAvailable('shareTargetPicker')) {
    const res = await liff.shareTargetPicker([message as any])
    return { success: !!res, mode: 'picker' }
  }

  throw new Error('目前環境不支援發送訊息（請在 LINE App 內開啟）')
}
