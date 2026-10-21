export function formatLocalDate(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function todayIso(): string {
  return formatLocalDate(new Date());
}

export function parseLocalDate(dInput: Date | string): Date {
  if (dInput instanceof Date) {
    return new Date(dInput.getFullYear(), dInput.getMonth(), dInput.getDate());
  }
  const [y, m, d] = dInput.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function getMonday(dInput: Date | string = new Date()): string {
  const d = parseLocalDate(dInput);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  d.setDate(diff);
  return formatLocalDate(d);
}

export function addDays(dateStr: string, days: number): string {
  const d = parseLocalDate(dateStr);
  d.setDate(d.getDate() + days);
  return formatLocalDate(d);
}

export function formatDayName(dateStr: string): string {
  const d = parseLocalDate(dateStr);
  return d.toLocaleDateString("en-US", { weekday: "short" });
}

export function formatMonthDay(dateStr: string): string {
  const d = parseLocalDate(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function getWeekDates(mondayStr: string): { date: string; dayName: string; formatted: string }[] {
  const dates = [];
  for (let i = 0; i < 7; i++) {
    const dStr = addDays(mondayStr, i);
    dates.push({
      date: dStr,
      dayName: formatDayName(dStr),
      formatted: formatMonthDay(dStr),
    });
  }
  return dates;
}

export function getMonthRange(dateStr: string): { startDate: string; endDate: string } {
  const d = parseLocalDate(dateStr);
  const year = d.getFullYear();
  const month = d.getMonth();
  const lastDay = new Date(year, month + 1, 0);

  const startIso = `${year}-${String(month + 1).padStart(2, "0")}-01`;
  const endIso = `${year}-${String(month + 1).padStart(2, "0")}-${String(lastDay.getDate()).padStart(2, "0")}`;
  return { startDate: startIso, endDate: endIso };
}
