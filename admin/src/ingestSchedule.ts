export type ClockSlot = {
  index: number;
  title: string;
  hour: number;
  minute: number;
  startMin: number;
};

const SLOT_TITLES = ["아침", "오후", "밤"];

export function parseScanHours(raw: string): ClockSlot[] {
  const slots: ClockSlot[] = [];
  for (const part of raw.split(",")) {
    const text = part.trim();
    const [hh, mm] = text.split(":");
    if (!hh || mm == null || !/^\d+$/.test(hh) || !/^\d+$/.test(mm)) continue;
    const hour = Number(hh);
    const minute = Number(mm);
    if (hour > 23 || minute > 59) continue;
    const index = slots.length;
    slots.push({
      index,
      title: SLOT_TITLES[index] ?? `${index + 1}번째`,
      hour,
      minute,
      startMin: hour * 60 + minute,
    });
  }
  return slots;
}

export function formatHm(hour: number, minute: number): string {
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

export function windowLabel(
  slot: ClockSlot | undefined,
  windowMinutes: number,
): string {
  if (!slot) return "";
  const end = slot.startMin + Math.max(1, windowMinutes);
  return `${formatHm(slot.hour, slot.minute)}–${formatHm(
    Math.floor(end / 60) % 24,
    end % 60,
  )}`;
}

export function kstNow(date: Date): {
  dateKey: string;
  minutes: number;
  label: string;
} {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? "00";
  const hour = Number(get("hour"));
  const minute = Number(get("minute"));
  return {
    dateKey: `${get("year")}-${get("month")}-${get("day")}`,
    minutes: hour * 60 + minute,
    label: formatHm(hour, minute),
  };
}

export function laneText(value: string): string {
  if (value === "korea") return "한국";
  if (value === "global") return "글로벌";
  if (value === "auto") return "분석이 적은 쪽";
  return value;
}

export function slotStatName(slot: string): string {
  const names: Record<string, string> = {
    morning: "아침",
    afternoon: "오후",
    night: "밤",
    hot: "Hot 추가 확인",
    account: "계정 타임라인",
    topic: "주제 검색",
    dynamic: "동적 검색",
    unscoped: "시각 표시 전",
    interval: "간격 수집",
  };
  return names[slot] ?? slot;
}

export type SlotPhase = "upcoming" | "open" | "done" | "passed";

export function doneThroughMinutes(
  lastKey: string | null,
  today: string,
): number | null {
  if (!lastKey?.startsWith(`${today}T`)) return null;
  const [hh, mm] = lastKey.slice(today.length + 1).split(":");
  if (!hh || !mm || !/^\d+$/.test(hh) || !/^\d+$/.test(mm)) return null;
  return Number(hh) * 60 + Number(mm);
}

export function slotPhase(
  slot: ClockSlot,
  windowMinutes: number,
  nowMinutes: number,
  doneThrough: number | null,
): SlotPhase {
  if (doneThrough != null && doneThrough >= slot.startMin) return "done";
  const end = slot.startMin + Math.max(1, windowMinutes);
  if (nowMinutes >= slot.startMin && nowMinutes < end) return "open";
  if (nowMinutes >= end) return "passed";
  return "upcoming";
}

export function phaseLabel(phase: SlotPhase): string {
  if (phase === "done") return "오늘 수집함";
  if (phase === "open") return "지금 이 구간";
  if (phase === "passed") return "시각은 지남";
  return "예정";
}
