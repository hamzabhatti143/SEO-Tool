"use client";

import * as React from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export type Column<T> = {
  key: string;
  header: React.ReactNode;
  cell: (row: T) => React.ReactNode;
  /** Provide to make the column sortable. */
  sortValue?: (row: T) => string | number | null;
  align?: "left" | "right" | "center";
  className?: string;
};

type SortState = { key: string; dir: "asc" | "desc" } | null;

const alignClass = {
  left: "text-left",
  right: "text-right",
  center: "text-center",
} as const;

/**
 * Generic table with client-side sorting and pagination. The parent owns
 * filtering/search; this handles presentation, sort, and paging.
 */
export function DataTable<T>({
  columns,
  rows,
  getRowKey,
  pageSize = 10,
  initialSort = null,
  emptyState,
  className,
  onSortedRowsChange,
}: {
  columns: Column<T>[];
  rows: T[];
  getRowKey: (row: T, index: number) => string;
  pageSize?: number;
  initialSort?: SortState;
  emptyState?: React.ReactNode;
  className?: string;
  /** Reports all rows in current sort order (post-filter, pre-pagination) —
   *  e.g. so a parent can export exactly what's shown. Pass a stable callback. */
  onSortedRowsChange?: (rows: T[]) => void;
}) {
  const [sort, setSort] = React.useState<SortState>(initialSort);
  const [page, setPage] = React.useState(0);

  // Reset to the first page whenever the underlying rows change (e.g. filter).
  React.useEffect(() => setPage(0), [rows]);

  const sorted = React.useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return rows;
    const factor = sort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = col.sortValue!(a);
      const bv = col.sortValue!(b);
      if (av === null) return 1;
      if (bv === null) return -1;
      if (av < bv) return -1 * factor;
      if (av > bv) return 1 * factor;
      return 0;
    });
  }, [rows, sort, columns]);

  // Surface the current sorted (filtered) rows to the parent for export, etc.
  React.useEffect(() => {
    onSortedRowsChange?.(sorted);
  }, [sorted, onSortedRowsChange]);

  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize));
  const current = Math.min(page, pageCount - 1);
  const pageRows = sorted.slice(
    current * pageSize,
    current * pageSize + pageSize
  );

  function toggleSort(key: string) {
    setSort((prev) =>
      prev?.key === key
        ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "asc" }
    );
  }

  if (rows.length === 0 && emptyState) {
    return <>{emptyState}</>;
  }

  return (
    <div className={cn("space-y-3", className)}>
      <div className="overflow-x-auto rounded-lg border bg-card shadow-soft">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              {columns.map((col) => {
                const active = sort?.key === col.key;
                const SortIcon = !active
                  ? ChevronsUpDown
                  : sort!.dir === "asc"
                    ? ArrowUp
                    : ArrowDown;
                return (
                  <th
                    key={col.key}
                    className={cn(
                      "px-4 py-3 font-medium",
                      alignClass[col.align ?? "left"],
                      col.className
                    )}
                  >
                    {col.sortValue ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(col.key)}
                        className={cn(
                          "inline-flex items-center gap-1 transition-colors hover:text-foreground",
                          active && "text-foreground"
                        )}
                      >
                        {col.header}
                        <SortIcon className="h-3.5 w-3.5" />
                      </button>
                    ) : (
                      col.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row, i) => (
              <tr
                key={getRowKey(row, i)}
                className="border-b transition-colors last:border-0 hover:bg-muted/40"
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cn(
                      "px-4 py-3",
                      alignClass[col.align ?? "left"],
                      col.className
                    )}
                  >
                    {col.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {sorted.length > pageSize && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Showing {current * pageSize + 1}–
            {Math.min((current + 1) * pageSize, sorted.length)} of{" "}
            {sorted.length}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={current === 0}
              onClick={() => setPage(current - 1)}
            >
              Previous
            </Button>
            <span className="tabular-nums">
              {current + 1} / {pageCount}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={current >= pageCount - 1}
              onClick={() => setPage(current + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
