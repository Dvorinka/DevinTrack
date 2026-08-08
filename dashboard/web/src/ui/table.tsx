import { cn } from '@/lib/utils'
import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes, TableHTMLAttributes } from 'react'

export function Table({ className, children, ...props }: TableHTMLAttributes<HTMLTableElement> & { children: ReactNode }) {
  return (
    <div className="w-full overflow-auto">
      <table className={cn('w-full text-sm', className)} {...props}>
        {children}
      </table>
    </div>
  )
}

export function Th({ className, children, ...props }: ThHTMLAttributes<HTMLTableCellElement> & { children: ReactNode }) {
  return (
    <th
      className={cn(
        'text-left font-medium text-muted-foreground text-xs uppercase tracking-wider px-3 py-2',
        className,
      )}
      {...props}
    >
      {children}
    </th>
  )
}

export function Td({ className, children, ...props }: TdHTMLAttributes<HTMLTableCellElement> & { children?: ReactNode }) {
  return (
    <td className={cn('px-3 py-2.5 border-t border-border', className)} {...props}>
      {children}
    </td>
  )
}

export function Tr({ className, children, ...props }: React.HTMLAttributes<HTMLTableRowElement> & { children?: ReactNode }) {
  return (
    <tr className={cn('transition-colors hover:bg-accent/40', className)} {...props}>
      {children}
    </tr>
  )
}
