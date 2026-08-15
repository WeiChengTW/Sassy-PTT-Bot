// 旅行類型權威清單（value/label/emoji）。
// 後端 travel/trip_types.py 持有對應的 VALID_TYPES，需手動同步。
export interface TripType {
  value: string
  label: string
  emoji: string
}

export const TRIP_TYPES: TripType[] = [
  { value: 'beach', label: '海灘度假', emoji: '🏖️' },
  { value: 'mountain', label: '登山健行', emoji: '🏔️' },
  { value: 'camping', label: '露營野營', emoji: '🏕️' },
  { value: 'hotspring', label: '溫泉放鬆', emoji: '♨️' },
  { value: 'city', label: '城市探索', emoji: '🏙️' },
  { value: 'food', label: '美食巡禮', emoji: '🍜' },
  { value: 'abroad', label: '國外出遊', emoji: '✈️' },
  { value: 'theme_park', label: '主題樂園', emoji: '🎢' },
  { value: 'culture', label: '歷史文化', emoji: '⛩️' },
  { value: 'roadtrip', label: '自駕公路', emoji: '🚗' },
  { value: 'other', label: '其他漫遊', emoji: '🎒' },
]

const BY_VALUE: Record<string, TripType> = Object.fromEntries(
  TRIP_TYPES.map((t) => [t.value, t]),
)

export function emojiFor(value: string): string {
  return BY_VALUE[value]?.emoji || '🎒'
}

export function labelFor(value: string): string {
  return BY_VALUE[value]?.label || value
}
