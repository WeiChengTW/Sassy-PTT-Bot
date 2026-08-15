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
    card: 'bg-gradient-to-br from-info-50/80 to-blue-50/50 border-info-100 shadow-card hover:border-info-200',
    icon: 'bg-info-100 text-info-700',
    name: 'text-slate-900',
    pill: 'bg-info-100/80 text-info-700 border border-info-200/60 font-semibold',
    date: 'text-info-600/70',
    dot: 'bg-info-500',
  },
  super_rare: {
    key: 'super_rare',
    zh: '極稀有',
    emoji: '🟡',
    order: 3,
    card: 'bg-gradient-to-br from-accent-50/90 to-amber-50/40 border-accent-200 shadow-card hover:border-accent-300',
    icon: 'bg-accent-100 text-accent-700',
    name: 'text-amber-950',
    pill: 'bg-accent-100 text-accent-700 border border-accent-300/80 font-bold',
    date: 'text-accent-600',
    dot: 'bg-accent-500 ring-2 ring-accent-200',
  },
  epic: {
    key: 'epic',
    zh: '史詩',
    emoji: '🟣',
    order: 4,
    card: 'bg-gradient-to-br from-purple-50/90 via-fuchsia-50/50 to-brand-50/60 border-purple-200 shadow-card badge-epic hover:border-purple-300',
    icon: 'bg-purple-100 text-purple-700',
    name: 'text-purple-950',
    pill: 'bg-purple-100 text-purple-700 border border-purple-200 font-bold',
    date: 'text-purple-600',
    dot: 'bg-purple-500 ring-2 ring-purple-200',
  },
  legendary: {
    key: 'legendary',
    zh: '傳說',
    emoji: '🔴',
    order: 5,
    card: 'bg-gradient-to-br from-rose-50/95 via-orange-50/40 to-amber-50/60 border-rose-300 shadow-card badge-legendary hover:border-rose-400',
    icon: 'bg-rose-100 text-rose-600',
    name: 'text-rose-950',
    pill: 'bg-gradient-to-r from-rose-500 to-amber-500 text-white font-black shadow-sm',
    date: 'text-rose-600 font-medium',
    dot: 'bg-rose-500 ring-2 ring-rose-300 animate-ping',
  },
}

export function rarityOf(key: string | null | undefined): RarityDef {
  return (key && RARITY[key as RarityKey]) || RARITY.common
}
