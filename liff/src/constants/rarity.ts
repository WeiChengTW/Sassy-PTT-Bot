// 稀有度 5 階權威清單（key/中文/emoji/Tailwind 樣式）。
// 後端 travel/badges.py 持有對應的 RARITY_LABEL / RARITY_CIRCLE，需手動同步。
export type RarityKey = 'common' | 'rare' | 'super_rare' | 'epic' | 'legendary'

export interface RarityDef {
  key: RarityKey
  zh: string
  emoji: string
  order: number
  card: string
  icon: string
  name: string
  pill: string
  date: string
  dot: string
}

export const RARITY: Record<RarityKey, RarityDef> = {
  common: {
    key: 'common', zh: '普通', emoji: '🟢', order: 1,
    card: 'bg-white border-gray-200',
    icon: 'bg-gray-100',
    name: 'text-gray-800',
    pill: 'bg-gray-100 text-gray-500',
    date: 'text-gray-400',
    dot: 'bg-gray-300',
  },
  rare: {
    key: 'rare', zh: '稀有', emoji: '🔵', order: 2,
    card: 'bg-blue-50 border-blue-200',
    icon: 'bg-blue-100',
    name: 'text-blue-900',
    pill: 'bg-blue-100 text-blue-600',
    date: 'text-blue-400',
    dot: 'bg-blue-400',
  },
  super_rare: {
    key: 'super_rare', zh: '極稀有', emoji: '🟣', order: 3,
    card: 'bg-purple-50 border-purple-300',
    icon: 'bg-purple-100',
    name: 'text-purple-900',
    pill: 'bg-purple-100 text-purple-600',
    date: 'text-purple-400',
    dot: 'bg-purple-500',
  },
  epic: {
    key: 'epic', zh: '史詩', emoji: '🔴', order: 4,
    card: 'bg-rose-50 border-rose-300 badge-epic',
    icon: 'bg-rose-100',
    name: 'text-rose-900',
    pill: 'bg-rose-100 text-rose-600',
    date: 'text-rose-400',
    dot: 'bg-rose-500',
  },
  legendary: {
    key: 'legendary', zh: '傳說', emoji: '🟡', order: 5,
    card: 'bg-amber-50 border-amber-300 badge-legendary',
    icon: 'bg-amber-100',
    name: 'text-amber-900',
    pill: 'bg-amber-100 text-amber-600',
    date: 'text-amber-400',
    dot: 'bg-amber-400',
  },
}

export function rarityOf(key: string | null | undefined): RarityDef {
  return (key && RARITY[key as RarityKey]) || RARITY.common
}
