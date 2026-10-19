import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useChartColors } from './useChartColors'

export interface TrendPoint { name: string; value: number }

export function TrendChart({ kind, data, unit = '', label }: { kind: 'bar' | 'area'; data: TrendPoint[]; unit?: string; label: string }) {
  const c = useChartColors()
  const common = (
    <>
      <CartesianGrid stroke={c.grid} vertical={false} />
      <XAxis dataKey="name" stroke={c.muted} tickLine={false} axisLine={false} fontSize={12} />
      <YAxis stroke={c.muted} tickLine={false} axisLine={false} fontSize={12} width={44} />
      <Tooltip
        formatter={(v) => [`${v}${unit}`, label]}
        contentStyle={{ background: c.surface, border: `1px solid ${c.grid}`, borderRadius: 16, color: c.ink }}
        cursor={{ fill: c.grid, opacity: 0.4 }}
      />
    </>
  )
  return (
    <div role="img" aria-label={`${label} chart, ${data.map((d) => `${d.name} ${d.value}${unit}`).join(', ')}`} className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        {kind === 'bar' ? (
          <BarChart data={data}>{common}<Bar dataKey="value" fill={c.accent} radius={[10, 10, 0, 0]} /></BarChart>
        ) : (
          <AreaChart data={data}>{common}<Area dataKey="value" stroke={c.ink} strokeWidth={2} fill={c.accent} fillOpacity={0.35} /></AreaChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}
