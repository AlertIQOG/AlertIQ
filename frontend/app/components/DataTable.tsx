import React from 'react';

// Definitions for the DataTable component, which is a reusable table component that can display any type of data based on the provided column definitions and data array.
export interface ColumnDef<T> {
  header: React.ReactNode;
  accessor?: keyof T; // Which property of the data object to display in this column (if renderCell is not provided)
  renderCell?: (row: T) => React.ReactNode; // A custom function for rendering the cell (like a button or tag)
  className?: string; // Additional CSS classes (for example, to set the column width w-24)
  sortKey?: string; // If set, the header is clickable to sort by this backend field
}

interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  rowClassName?: (row: T) => string;
  // Sorting is controlled by the parent (applied server-side). When no column
  // is actively sorted, the default order is shown on defaultSortKey.
  sortBy?: string;
  sortDir?: 'asc' | 'desc';
  defaultSortKey?: string;
  defaultSortDir?: 'asc' | 'desc';
  onSort?: (key: string) => void;
}

export default function DataTable<T>({ columns, data, onRowClick, rowClassName, sortBy, sortDir, defaultSortKey, defaultSortDir, onSort }: DataTableProps<T>) {
  // Fall back to the default order for the indicator when nothing is actively sorted.
  const activeKey = sortBy ?? defaultSortKey;
  const activeDir = sortBy ? sortDir : defaultSortDir;
  const isDefault = !sortBy;
  return (
  <div className="w-full bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
    <div className="w-full max-h-[60vh] overflow-auto custom-scrollbar">
      <table className="w-full text-left text-base">
        <thead className="bg-slate-800/50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-800">
          <tr>
            {columns.map((col, idx) => {
              const sortable = Boolean(col.sortKey && onSort);
              const active = sortable && col.sortKey === activeKey;
              return (
                <th key={idx} className={`px-4 py-3 ${col.className || ''}`}>
                  {sortable ? (
                    <button
                      type="button"
                      onClick={() => onSort!(col.sortKey!)}
                      className="group inline-flex items-center gap-1.5 uppercase font-semibold hover:text-slate-300 transition"
                    >
                      {col.header}
                      <i
                        className={`fas text-[11px] ${
                          active
                            ? `${activeDir === 'asc' ? 'fa-sort-up' : 'fa-sort-down'} ${isDefault ? 'text-slate-500' : 'text-indigo-400'}`
                            : 'fa-sort text-slate-600 group-hover:text-slate-400'
                        }`}
                      ></i>
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 text-slate-300">
          {data.map((row, rowIndex) => (
            <tr
              key={rowIndex}
              onClick={() => onRowClick && onRowClick(row)}
              className={`hover:bg-slate-800/50 transition cursor-pointer ${rowClassName ? rowClassName(row) : ''}`}
            >
              {columns.map((col, colIndex) => (
                <td key={colIndex} className={`px-4 py-3 ${col.className || ''}`}>
                  {/* If the column has a custom render function (like a Toggle) - use it.
                      Otherwise, simply display the regular text from the data object */}
                  {col.renderCell 
                    ? col.renderCell(row) 
                    : String(row[col.accessor as keyof T] || '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}