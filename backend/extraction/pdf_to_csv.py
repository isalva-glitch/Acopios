import pdfplumber
import csv
import sys
import os

def convert_pdf_to_csv(pdf_path, csv_path):
    """
    Extracts all tables from a PDF and writes them to a CSV file.
    Preserves table structure and separates tables with empty lines.
    """
    print(f"Converting {pdf_path} to {csv_path}...")
    
    with pdfplumber.open(pdf_path) as pdf:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 1. Extract First Page Text (Header Info) and write as a special block
            # This covers Client, Obra, Date, etc. which are often not in tables
            if len(pdf.pages) > 0:
                page0 = pdf.pages[0]
                text = page0.extract_text()
                if text:
                    writer.writerow(["### RAW TEXT PAGE 1 ###"])
                    for line in text.split('\n'):
                        writer.writerow([line])
                    writer.writerow([])
                    writer.writerow(["### TABLES START ###"])
                    writer.writerow([])

            # 2. Extract Tables from ALL pages
            for p_idx, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                
                if not tables:
                    continue
                    
                writer.writerow([f"### PAGE {p_idx + 1} ###"])
                
                for t_idx, table in enumerate(tables):
                    writer.writerow([f"--- Table {t_idx + 1} ---"])
                    for row in table:
                        # Clean None values to empty strings
                        clean_row = [cell if cell is not None else "" for cell in row]
                        writer.writerow(clean_row)
                    writer.writerow([]) # Empty row between tables
                
                writer.writerow([]) # Empty row between pages

    print("Conversion complete.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python pdf_to_csv.py <input_pdf> <output_csv>")
        # Default for testing in this environment
        input_pdf = "/app/sample.pdf"
        output_csv = "/app/debug_output.csv"
        print(f"Using default paths: {input_pdf} -> {output_csv}")
    else:
        input_pdf = sys.argv[1]
        output_csv = sys.argv[2]
        
    convert_pdf_to_csv(input_pdf, output_csv)
