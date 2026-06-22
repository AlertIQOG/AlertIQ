import React from 'react';

// Definitions for the DataTable component, which is a reusable table component that can display any type of data based on the provided column definitions and data array.
export interface ColumnDef<T> {
  header: React.ReactNode;
  accessor?: keyof T;
  renderCell?: (row: T) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  rowClassName?: (row: T) => string;
}

export default function DataTable<T>({ columns, data, onRowClick, rowClassName }: DataTableProps<T>) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
      <div className="overflow-x-auto custom-scrollbar">
      <table className="w-full text-left min-w-max">
        <thead className="bg-slate-800/50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-800">
          <tr>
            {columns.map((col, idx) => (
              <th key={idx} className={`px-4 py-3 ${col.className || ''}`}>
                {col.header}
              </th>
            ))}
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
                    : String(row[col.accessor as keyof T])}
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