import React, { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type { PlanEntry } from "../types";
import {
  getMonthRange,
  getMonday,
  addDays,
  parseLocalDate,
  formatLocalDate,
} from "../utils/date";

interface CalendarViewProps {
  weekStart?: string;
  onNavigateToWeek?: (weekStart: string) => void;
  onError: (msg: string) => void;
}

export const CalendarView: React.FC<CalendarViewProps> = ({
  weekStart: initialWeekStart,
  onNavigateToWeek,
  onError,
}) => {
  const [currentDate, setCurrentDate] = useState<Date>(() => new Date());
  const [viewMode, setViewMode] = useState<"month" | "week">("month");
  const [entries, setEntries] = useState<PlanEntry[]>([]);
  const [loading, setLoading] = useState(false);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const loadRange = useCallback(async () => {
    setLoading(true);
    const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-15`;
    const { startDate, endDate } = getMonthRange(dateStr);

    try {
      const data = await api.getPlanRange(startDate, endDate);
      setEntries(data);
    } catch (err: any) {
      onError(err.message || "Failed to load calendar range");
    } finally {
      setLoading(false);
    }
  }, [year, month, onError]);

  useEffect(() => {
    loadRange();
  }, [loadRange]);

  const handlePrevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
  };

  const handleNextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
  };

  const handleToday = () => {
    setCurrentDate(new Date());
  };

  // Month title
  const monthName = currentDate.toLocaleString("en-US", {
    month: "long",
    year: "numeric",
  });

  const firstDayOfMonth = new Date(year, month, 1).getDay(); // 0 is Sun
  // Monday-based indexing: Mon=0, Tue=1, ... Sun=6
  const startOffset = (firstDayOfMonth + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const monthDays: {
    dateStr: string;
    dayNum: number;
    inMonth: boolean;
  }[] = [];

  // Padding days from previous month
  const prevMonthDays = new Date(year, month, 0).getDate();
  for (let i = startOffset - 1; i >= 0; i--) {
    const d = prevMonthDays - i;
    const prevDate = new Date(year, month - 1, d);
    monthDays.push({
      dateStr: formatLocalDate(prevDate),
      dayNum: d,
      inMonth: false,
    });
  }

  // Days of current month
  for (let d = 1; d <= daysInMonth; d++) {
    const curDate = new Date(year, month, d);
    monthDays.push({
      dateStr: formatLocalDate(curDate),
      dayNum: d,
      inMonth: true,
    });
  }

  // Padding days to fill remaining week grid (multiples of 7)
  const remaining = (7 - (monthDays.length % 7)) % 7;
  for (let d = 1; d <= remaining; d++) {
    const nextDate = new Date(year, month + 1, d);
    monthDays.push({
      dateStr: formatLocalDate(nextDate),
      dayNum: d,
      inMonth: false,
    });
  }

  const activeWeekStart = initialWeekStart || getMonday(currentDate);
  const weekDays: {
    dateStr: string;
    dayNum: number;
    inMonth: boolean;
  }[] = Array.from({ length: 7 }, (_, i) => {
    const dateStr = addDays(activeWeekStart, i);
    const d = parseLocalDate(dateStr);
    return {
      dateStr,
      dayNum: d.getDate(),
      inMonth: d.getMonth() === month,
    };
  });

  const calendarDays = viewMode === "week" ? weekDays : monthDays;

  const handleDayClick = (dateStr: string) => {
    if (onNavigateToWeek) {
      onNavigateToWeek(getMonday(dateStr));
    }
  };

  return (
    <div className="calendar-view">
      <header className="calendar-header">
        <div className="month-nav">
          <button type="button" onClick={handlePrevMonth} className="btn-secondary">
            ← Prev Month
          </button>
          <button type="button" onClick={handleToday} className="btn-secondary">
            Today
          </button>
          <button type="button" onClick={handleNextMonth} className="btn-secondary">
            Next Month →
          </button>
          <h2 className="month-title">{monthName}</h2>
        </div>

        <div className="view-mode-toggle">
          <button
            type="button"
            className={`btn-toggle ${viewMode === "month" ? "active" : ""}`}
            onClick={() => setViewMode("month")}
          >
            Month View
          </button>
          <button
            type="button"
            className={`btn-toggle ${viewMode === "week" ? "active" : ""}`}
            onClick={() => setViewMode("week")}
          >
            Week View
          </button>
        </div>
      </header>

      {loading && <div className="loading-indicator">Loading calendar...</div>}

      <div className="calendar-grid">
        <div className="calendar-weekdays">
          <span>Mon</span>
          <span>Tue</span>
          <span>Wed</span>
          <span>Thu</span>
          <span>Fri</span>
          <span>Sat</span>
          <span>Sun</span>
        </div>

        <div className="calendar-days">
          {calendarDays.map((cd) => {
            const dayEntries = entries.filter((e) => e.date === cd.dateStr);

            return (
              <div
                key={cd.dateStr}
                className={`calendar-cell ${cd.inMonth ? "in-month" : "out-month"}`}
                onClick={() => handleDayClick(cd.dateStr)}
              >
                <div className="cell-header">
                  <span className="day-number">{cd.dayNum}</span>
                </div>

                <div className="cell-entries">
                  {dayEntries.map((entry) => {
                    const isCooked = Boolean(entry.cooked);
                    return (
                      <div
                        key={entry.id}
                        className={`calendar-entry ${isCooked ? "entry-cooked" : "entry-planned"}`}
                        title={`${entry.title || entry.recipe_title || "Recipe"} (${isCooked ? "Cooked" : "Planned"})`}
                      >
                        <span className="entry-title">
                          {entry.title || entry.recipe_title || "Recipe"}
                        </span>
                        {isCooked ? (
                          <span className="badge badge-cooked">Cooked</span>
                        ) : (
                          <span className="badge badge-planned">Planned</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
