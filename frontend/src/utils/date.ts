export function getMonday(dInput: Date | string = new Date()): string {
  const d = typeof dInput === "string" ? new Date(dInput + "T00:00:00") : new Date(dInput);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(d.setDate(diff));
  return monday.toISOString().slice(0, 10);
}

export function addDays(dateStr: string, days: number): string {
  const d = new Date(dateStr + "T00:00:00");
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function formatDayName(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short" });
}

export function formatMonthDay(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
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
  const d = new Date(dateStr + "T00:00:00");
  const year = d.getFullYear();
  const month = d.getMonth();
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);

  const startIso = `${year}-${String(month + 1).padStart(2, "0")}-01`;
  const endIso = `${year}-${String(month + 1).padStart(2, "0")}-${String(lastDay.getDate()).padStart(2, "0")}`;
  return { startDate: startIso, endDate: endIso };
}
