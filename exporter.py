"""
Exporter: Handles exporting scraped leads to Excel (.xlsx) and CSV
Configured via settings.py and .env
"""

import pandas as pd
from settings import DATA_COLUMNS, EXCEL_OUTPUT_PATH, CSV_OUTPUT_PATH
from logger import logger

def export_data(data, excel_path=EXCEL_OUTPUT_PATH, csv_path=CSV_OUTPUT_PATH):
    """
    Exports a list of dict records to styled Excel and CSV files.
    """
    if not data:
        logger.warning("No data provided to export.")
        return None

    df = pd.DataFrame(data)

    # Ensure all columns exist and are ordered
    for col in DATA_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[DATA_COLUMNS]

    # Clean duplicates based on Profile Link
    initial_len = len(df)
    df.drop_duplicates(subset=["Profile Link"], inplace=True)
    if len(df) < initial_len:
        logger.info(f"Removed {initial_len - len(df)} duplicate records.")

    # 1. Export CSV
    try:
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        logger.info(f"CSV file exported to: {csv_path}")
    except Exception as e:
        logger.error(f"CSV export error: {e}")

    # 2. Export Styled Excel
    try:
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Leads_Data', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Leads_Data']

            # Openpyxl Styles
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

            header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            border_side = Side(border_style="thin", color="D9D9D9")
            cell_border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)
            row_fill_alt = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")

            # Style header
            for col_idx in range(1, len(DATA_COLUMNS) + 1):
                cell = worksheet.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            # Auto-fit column widths & style data rows
            for col_idx, col_name in enumerate(DATA_COLUMNS, 1):
                max_len = len(col_name)
                for row_idx in range(2, len(df) + 2):
                    cell = worksheet.cell(row=row_idx, column=col_idx)
                    cell.border = cell_border
                    val = str(cell.value or "")
                    max_len = max(max_len, min(len(val), 60))
                    
                    # Alternate row coloring
                    if row_idx % 2 == 0:
                        cell.fill = row_fill_alt
                        
                    # Alignment
                    if col_name in ["Pincode", "City / Locality", "State"]:
                        cell.alignment = Alignment(horizontal="center", vertical="top")
                    elif col_name in ["Full Address", "Description"]:
                        cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
                    else:
                        cell.alignment = Alignment(horizontal="left", vertical="top")

                col_letter = worksheet.cell(row=1, column=col_idx).column_letter
                worksheet.column_dimensions[col_letter].width = max(max_len + 3, 14)

            # Header row height
            worksheet.row_dimensions[1].height = 28

        logger.info(f"Styled Excel file exported to: {excel_path}")
    except Exception as e:
        logger.warning(f"Excel styling failed: {e}. Falling back to standard export.")
        df.to_excel(excel_path, index=False)

    logger.info(f"DONE! Total {len(df)} leads successfully exported.")
    return df
