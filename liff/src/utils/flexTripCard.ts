// 把旅行事件 detail 轉成 LINE Messaging API 規範的純 JSON Flex Message，
// 供 liff.sendMessages / liff.shareTargetPicker 使用（不是 SDK 物件形式）。
import { rarityOf } from '@/constants/rarity'
import { emojiFor, labelFor } from '@/constants/tripTypes'

// 稀有度主題色（hex）。rarity.ts 用的是 Tailwind class，Flex 需要 hex——
// 這份對照需與 constants/rarity.ts 手動同步。
const RARITY_HEX: Record<string, string> = {
  common: '#9ca3af',
  rare: '#3b82f6',
  super_rare: '#a855f7',
  epic: '#f43f5e',
  legendary: '#f59e0b',
}

function fmtDate(ts: number): string {
  const d = new Date(ts * 1000)
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}

function dateRange(t: any): string {
  if (!t?.start_date) return ''
  const start = fmtDate(t.start_date)
  if (!t.end_date || t.end_date === t.start_date) return start
  return `${start} – ${fmtDate(t.end_date)}`
}

export interface FlexMessage {
  type: 'flex'
  altText: string
  contents: any
}

/**
 * 依 detail（含 trip / participants / stats）產生事件回顧小卡。
 * 對缺欄位（timeline 情境的空 stats/participants）做防呆，缺則略過區塊。
 */
export function buildTripFlex(detail: any): FlexMessage {
  const trip = detail?.trip ?? {}
  const participants: any[] = detail?.participants ?? []
  const messageCount: number | undefined = detail?.stats?.message_count

  const rarity = rarityOf(trip.rarity)
  const accent = RARITY_HEX[rarity.key] || RARITY_HEX.common
  const title: string = trip.title || '旅行回顧'
  const location: string = trip.location || ''
  const range = dateRange(trip)
  const liffId = import.meta.env.VITE_LIFF_ID as string

  const altText = location
    ? `[旅行回顧] ${title}（${location}）`
    : `[旅行回顧] ${title}`

  // ── Body 內容區塊（逐一防呆組裝） ──
  const bodyContents: any[] = []

  if (range) {
    bodyContents.push(infoRow('🗓️', range))
  }

  // 類型 Pill
  const tripTypes: string[] = Array.isArray(trip.trip_types) ? trip.trip_types : []
  if (tripTypes.length) {
    bodyContents.push({
      type: 'box',
      layout: 'horizontal',
      spacing: 'xs',
      wrap: true,
      contents: tripTypes.slice(0, 4).map((ty) => ({
        type: 'text',
        text: `${emojiFor(ty)} ${labelFor(ty)}`,
        size: 'xs',
        color: accent,
        flex: 0,
        margin: 'xs',
      })),
    })
  }

  // 參與者摘要
  if (participants.length) {
    const names = participants
      .slice(0, 3)
      .map((p) => p.user_name || p.user_id)
      .filter(Boolean)
      .join('、')
    const extra = participants.length > 3 ? ` 等 ${participants.length} 人` : ''
    bodyContents.push(infoRow('👥', `${names}${extra}`))
  }

  // 訊息統計
  if (typeof messageCount === 'number') {
    bodyContents.push(infoRow('💬', `${messageCount} 則訊息`))
  }

  const bubble = {
    type: 'bubble',
    header: {
      type: 'box',
      layout: 'vertical',
      backgroundColor: accent,
      paddingAll: '16px',
      contents: [
        {
          type: 'text',
          text: `${rarity.emoji} ${rarity.zh}`,
          size: 'xs',
          color: '#ffffffcc',
          weight: 'bold',
        },
        {
          type: 'text',
          text: title,
          size: 'lg',
          weight: 'bold',
          color: '#ffffff',
          wrap: true,
          margin: 'sm',
        },
        ...(location
          ? [{
              type: 'text',
              text: `📍 ${location}`,
              size: 'sm',
              color: '#ffffffdd',
              margin: 'xs',
            }]
          : []),
      ],
    },
    body: {
      type: 'box',
      layout: 'vertical',
      spacing: 'sm',
      paddingAll: '16px',
      contents: bodyContents.length
        ? bodyContents
        : [{ type: 'text', text: '一段值得回味的旅程 ✨', size: 'sm', color: '#888888', wrap: true }],
    },
    footer: {
      type: 'box',
      layout: 'vertical',
      paddingAll: '12px',
      contents: [
        {
          type: 'button',
          style: 'primary',
          color: accent,
          height: 'sm',
          action: {
            type: 'uri',
            label: '🔍 開啟回顧',
            uri: `https://liff.line.me/${liffId}/trips/${trip.id}`,
          },
        },
      ],
    },
  }

  return { type: 'flex', altText, contents: bubble }
}

function infoRow(icon: string, text: string): any {
  return {
    type: 'box',
    layout: 'baseline',
    spacing: 'sm',
    contents: [
      { type: 'text', text: icon, size: 'sm', flex: 0 },
      { type: 'text', text, size: 'sm', color: '#555555', wrap: true, flex: 1 },
    ],
  }
}
