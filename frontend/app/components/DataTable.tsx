import React from 'react';

// Definitions for the DataTable component, which is a reusable table component that can display any type of data based on the provided column definitions and data array.
export interface ColumnDef<T> {
  header: string;
  accessor?: keyof T; // Which property of the data object to display in this column (if renderCell is not provided)
  renderCell?: (row: T) => React.ReactNode; // A custom function for rendering the cell (like a button or tag)
  className?: string; // Additional CSS classes (for example, to set the column width w-24)
}

interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
}

export default function DataTable<T>({ columns, data, onRowClick }: DataTableProps<T>) {
  return (
    <div className="w-full h-full bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm flex flex-col">
      <div className="w-full overflow-x-auto custom-scrollbar flex-1">
      <table className="w-full text-left">
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
              className="hover:bg-slate-800/50 transition cursor-pointer"
            >
              {columns.map((col, colIndex) => (
                <td key={colIndex} className="px-4 py-3">
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