import { useMemo, useState, type ReactNode } from 'react'
import { ArrowDown, ArrowUp, Search } from 'lucide-react'
import { EmptyState } from '@/components/ui/EmptyState'

export type Row = Record<string, string | number>
export interface Column { key: string; header: string; render?: (row: Row) => ReactNode; align?: 'right' }

interface DataTableProps {
  caption: string
  columns: Column[]
  rows: Row[]
  /** Column used by the filter dropdown (e.g. 'status'). */
  filterKey?: string
  onRowClick?: (row: Row) => void
}

/** Client-side search, single-column filter and sortable headers. Server-side paging arrives with the real APIs. */
export function DataTable({ caption, columns, rows, filterKey, onRowClick }: DataTableProps) {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('all')
  const [sort, setSort] = useState<{ key: string; dir: 'asc' | 'desc' } | null>(null)

  const options = useMemo(() => (filterKey ? Array.from(new Set(rows.map((r) => String(r[filterKey])))) : []), [rows, filterKey])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    let out = rows.filter((r) => (filter === 'all' || String(r[filterKey ?? '']) === filter) && (!q || Object.values(r).some((v) => String(v).toLowerCase().includes(q))))
    if (sort) {
      out = [...out].sort((a, b) => {
        const x = a[sort.key], y = b[sort.key]
        const cmp = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y))
        return sort.dir === 'asc' ? cmp : -cmp
      })
    }
    return out
  }, [rows, query, filter, sort, filterKey])

  const toggleSort = (key: string) =>
    setSort((s) => (s?.key !== key ? { key, dir: 'asc' } : s.dir === 'asc' ? { key, dir: 'desc' } : null))

  return (
    <div className="flex flex-col gap-u8">
      <div className="flex flex-wrap gap-u4">
        <label className="relative min-w-[12rem] flex-1">
          <span className="sr-only">Search {caption}</span>
          <Search className="pointer-events-none absolute left-u7 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search"
            className="h-11 w-full rounded-ctl border border-line bg-surface pl-u17 pr-u6 placeholder:text-muted"
          />
        </label>
        {filterKey && (
          <label>
            <span className="sr-only">Filter by {filterKey}</span>
            <select value={filter} onChange={(e) => setFilter(e.target.value)} className="h-11 rounded-ctl border border-line bg-surface px-u6">
              <option value="all">All {filterKey}</option>
              {options.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </label>
        )}
      </div>

      {visible.length === 0 ? (
        <EmptyState title="No matching records" description="Clear the search or filter to see every record again." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] border-collapse text-left">
            <caption className="sr-only">{caption}</caption>
            <thead>
              <tr className="border-b border-line text-sm text-muted">
                {columns.map((c) => (
                  <th
                    key={c.key}
                    scope="col"
                    aria-sort={sort?.key === c.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                    className={`px-u4 py-u5 font-medium ${c.align === 'right' ? 'text-right' : ''}`}
                  >
                    <button onClick={() => toggleSort(c.key)} className="inline-flex min-h-[44px] items-center gap-1 hover:text-ink">
                      {c.header}
                      {sort?.key === c.key && (sort.dir === 'asc' ? <ArrowUp className="h-3 w-3" aria-hidden /> : <ArrowDown className="h-3 w-3" aria-hidden />)}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((row, i) => (
                <tr key={`${row[columns[0].key]}-${i}`} className="border-b border-line last:border-0">
                  {columns.map((c, ci) => (
                    <td key={c.key} className={`px-u4 py-u6 ${c.align === 'right' ? 'text-right tabular-nums' : ''}`}>
                      {ci === 0 && onRowClick ? (
                        <button onClick={() => onRowClick(row)} className="min-h-[44px] font-medium underline-offset-4 hover:underline">
                          {c.render ? c.render(row) : row[c.key]}
                        </button>
                      ) : c.render ? c.render(row) : row[c.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
