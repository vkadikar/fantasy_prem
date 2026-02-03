
import sys
from pypdf import PdfReader

def extract_text(pdf_path):
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
    except Exception as e:
        return str(e)

if __name__ == "__main__":
    pdf_path = '/Users/varunkadikar/Desktop/personal_projects/Antigravity/sports_analytics/documents/Fantasy Prem 2025-26.pdf'
    print(extract_text(pdf_path))
