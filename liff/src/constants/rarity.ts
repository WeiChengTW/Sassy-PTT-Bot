// 稀有度 5 階權威清單（漸層視覺升級版）
// key / 中文 / emoji / Tailwind 樣式
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
  badgeGlow?: string
}

export const RARITY: Record<RarityKey, RarityDef> = {
  common: {
    key: 'common',
    zh: '普通',
    emoji: '⚪',
    order: 1,
    card: 'bg-white border-slate-200/80 shadow-card hover:border-slate-300',
    icon: 'bg-slate-100 text-slate-600',
    name: 'text-slate-800',
    pill: 'bg-slate-100 text-slate-600 border border-slate-200',
    date: 'text-slate-400',
    dot: 'bg-slate-300',
  },
  rare: {
    key: 'rare',
    zh: '稀有',
    emoji: '🔵',
    order: 2,
    card: 'bg-gradient-to-br from-blue-50 to-sky-100/70 border-blue-200 shadow-card hover:border-blue-300',
    icon: 'bg-blue-100 text-blue-700',
    name: 'text-blue-950',
    pill: 'bg-blue-100 text-blue-700 border border-blue-200 font-bold',
    date: 'text-blue-600/80',
    dot: 'bg-blue-500',
  },
  super_rare: {
    key: 'super_rare',
    zh: '極稀有',
    emoji: '🟡',
    order: 3,
    card: 'bg-gradient-to-br from-amber-100/90 via-amber-50/90 to-yellow-100/80 border-amber-300 shadow-card hover:border-amber-400',
    icon: 'bg-amber-200/80 text-amber-800',
    name: 'text-amber-950',
    pill: 'bg-amber-200/90 text-amber-900 border border-amber-300 font-black shadow-2xs',
    date: 'text-amber-700 font-medium',
    dot: 'bg-amber-500 ring-2 ring-amber-200',
  },
  epic: {
    key: 'epic',
    zh: '史詩',
    emoji: '🟣',
    order: 4,
    card: 'bg-gradient-to-br from-purple-100/80 via-fuchsia-50/80 to-purple-50 border-purple-300 shadow-card badge-epic hover:border-purple-400',
    icon: 'bg-purple-200/80 text-purple-800',
    name: 'text-purple-950',
    pill: 'bg-purple-200/90 text-purple-900 border border-purple-300 font-black shadow-2xs',
    date: 'text-purple-700 font-medium',
    dot: 'bg-purple-500 ring-2 ring-purple-200',
  },
  legendary: {
    key: 'legendary',
    zh: '傳說',
    emoji: '🔴',
    order: 5,
    card: 'bg-gradient-to-br from-rose-100/90 via-rose-50/90 to-orange-100/70 border-rose-300 shadow-card badge-legendary hover:border-rose-400',
    icon: 'bg-rose-200/80 text-rose-800',
    name: 'text-rose-950',
    pill: 'bg-gradient-to-r from-rose-500 to-amber-500 text-white font-black shadow-2xs',
    date: 'text-rose-700 font-semibold',
    dot: 'bg-rose-500 ring-2 ring-rose-300 dot-ping-slow',
  },
}

export function rarityOf(key: string | null | undefined): RarityDef {
  return (key && RARITY[key as RarityKey]) || RARITY.common
}
