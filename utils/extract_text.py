import pymupdf4llm
import pathlib
import os 
from pathlib import Path
from utils.which_type import get_the_list_of_types
from docx import Document


def docx_to_markdown(file_path: str) -> str:
    doc = Document(file_path)
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = para.style.name
        if "Heading 1" in style:   lines.append(f"# {text}")
        elif "Heading 2" in style: lines.append(f"## {text}")
        elif "Heading 3" in style: lines.append(f"### {text}")
        else:                      lines.append(text)
    return "\n".join(lines)


def extract_text_for_paper(form_path_list: list):
    for form_path in form_path_list:
        file_path = Path(form_path)
        root, extension = os.path.splitext(file_path.name)

        if extension.lower() == ".docx":
            markdown_text = docx_to_markdown(form_path)
        else:
            markdown_text = pymupdf4llm.to_markdown(form_path)

        output_path = Path(f"output_of_forms/{root}.md")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        print(f"Converted: {file_path.name} → {output_path}")


if __name__ == "__main__": 
    data_path = "data"
    forms = get_the_list_of_types(data_path)
    unknown = forms["unknown"]
    extract_text_for_paper(unknown)