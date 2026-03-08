import json
from pathlib import Path
import os
from openai import OpenAI
from dotenv import load_dotenv
from pypdf import PdfReader
from pdf2image import convert_from_path
import base64
from io import BytesIO
from utils.which_type import get_the_list_of_types

load_dotenv()

client = OpenAI()



# ── helpers ───────────────────────────────────────────────────────────────────

def find_paper_title(md_text: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """You are responsible for finding the paper title in the given text.
                Return ONLY a JSON object with no extra text, no markdown, no explanation.
                Format: {"paper_title_exists": bool, "paper_title_name": str}
                If no paper title is found, return: {"paper_title_exists": false, "paper_title_name": ""}"""
            },
            {"role": "user", "content": md_text}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)


def pdf_pages_to_base64(pdf_path: str, num_pages: int) -> list[str]:
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    first_page = max(1, total_pages - num_pages + 1)

    images = convert_from_path(pdf_path, first_page=first_page, last_page=total_pages, dpi=150)

    base64_images = []
    for image in images:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        base64_images.append(base64.b64encode(buffer.getvalue()).decode("utf-8"))

    return base64_images


def check_signature_in_pages(pdf_path: str) -> dict:
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    num_pages = min(5, total_pages)

    base64_images = pdf_pages_to_base64(pdf_path, num_pages=num_pages)

    content = []
    for i, img_b64 in enumerate(base64_images):
        content.append({"type": "text", "text": f"Page {i + 1}:"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}})
    content.append({
        "type": "text",
        "text": "Check these pages and find all author signatures, the co-author's name and surname, and the date."
    })

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """You are responsible for detecting author signatures and co-author details in the given pages.
                This form may contain signatures from multiple different authors.
                Look for: all handwritten or digital signatures, the co-author's name and surname, and the date.
                Return ONLY a JSON object with no extra text, no markdown, no explanation.
                Format:
                {
                    "signatures_exist": bool,
                    "signature_of_authors": List[str],
                    "co_author_name_exists": bool,
                    "name_of_co_author": str,
                    "co_author_surname_exists": bool,
                    "surname_of_co_author": str,
                    "date_exists": bool,
                    "date": str
                }
                - "signature_of_authors" should be a list of author names/identifiers whose signatures are present (e.g. ["Author 1", "John Doe"]).
                - Use empty string "" for str fields if not found.
                - Use empty list [] for "signature_of_authors" if no signatures are found."""
            },
            {"role": "user", "content": content}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)


# ── main checker ──────────────────────────────────────────────────────────────

def check_3c_form(main_name: str, md_dir: str = "output_of_forms", pdf_dir: str = "data") -> dict:
    md_file_path  = f"{md_dir}/{main_name}.md"
    pdf_file_path = f"{pdf_dir}/{main_name}.pdf"

    with open(md_file_path, "r") as f:
        md_text = f.read()

    paper_title = find_paper_title(md_text)
    signature   = check_signature_in_pages(pdf_file_path)

    return {
        "form_name": main_name,
        **paper_title,
        **signature,
    }


# ── main loop ─────────────────────────────────────────────────────────────────
if __name__ == "__main__": 
    data_path = "data"
    form_dict = get_the_list_of_types(data_path)
    _3c_ = form_dict["3c"]
    
    all_results_3c = {}

    for form in _3c_:
        file_path = Path(form)
        main_name, _ = os.path.splitext(file_path.name)

        print(f"Processing: {main_name}")
        result = check_3c_form(main_name)
        all_results_3c[main_name] = result

    print("\n===== 3C RESULTS =====")
    print(json.dumps(all_results_3c, indent=2))