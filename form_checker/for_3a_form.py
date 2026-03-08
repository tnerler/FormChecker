import re
from utils.which_type import get_the_list_of_types
from pathlib import Path
import os 
import json
from openai import OpenAI
from dotenv import load_dotenv
from pypdf import PdfReader
from pdf2image import convert_from_path
import base64
from io import BytesIO

load_dotenv()
client = OpenAI()


# ── helpers ──────────────────────────────────────────────────────────────────

def find_corresponding_author(md_text: str) -> dict:
    sentences = re.split(r'(?<=[.!?])\s+', md_text)
    matches = [s for s in sentences if "corresponding author" in s.lower()]

    if not matches:
        return {"corresponding_author_exists": False, "corresponding_author_name": ""}

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """You are responsible to find the corresponding author's name in the given text.
                Return ONLY a JSON object with no extra text, no markdown, no explanation.
                Format: {"corresponding_author_exists": bool, "corresponding_author_name": str}
                If no corresponding author is found, return: {"corresponding_author_exists": false, "corresponding_author_name": ""}"""
            },
            {"role": "user", "content": " ".join(matches)}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)


def get_text_under_header(md_text: str, header: str) -> str:
    escaped_header = re.escape(header)
    pattern = rf"{escaped_header}\s*\n(.*?)(?=\n\*\*\d+\.\*\*|\Z)"
    match = re.search(pattern, md_text, re.DOTALL)
    return match.group(1).strip() if match else ""


def find_title_in_1(md_text: str) -> dict:
    sentences = re.split(r'(?<=[.!?])\s+', md_text)
    matches = [s for s in sentences if "the work may be published in the book series" in s.lower()]

    if not matches:
        return {"title_in_1_exists": False, "title_in_1_name": ""}

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """You are responsible for finding the book series title in the given sentence.
                The title is usually found inside square brackets [] in a sentence like:
                'The work may be published in the book series [TITLE HERE]'.
                Return ONLY a JSON object with no extra text, no markdown, no explanation.
                Format: {"title_in_1_exists": bool, "title_in_1_name": str}
                If no title is found, return: {"title_in_1_exists": false, "title_in_1_name": ""}"""
            },
            {"role": "user", "content": " ".join(matches)}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)



def find_title_in_section(md_text: str) -> dict:
    section_text = get_text_under_header(md_text, "**2.** **Subject of the Agreement**")

    if not section_text:
        return {"title_in_2_exists": False, "title_in_2_name": ""}

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """You are responsible for finding the title/name of the agreement in the given text.
                Return ONLY a JSON object with no extra text, no markdown, no explanation.
                Format: {"title_in_2_exists": bool, "title_in_2_name": str}
                If no title is found, return: {"title_in_2_exists": false, "title_in_2_name": ""}"""
            },
            {"role": "user", "content": section_text}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)


def pdf_pages_to_base64(pdf_path: str, num_pages: int = 5) -> list[str]:
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
    base64_images = pdf_pages_to_base64(pdf_path, num_pages=5)

    content = []
    for i, img_b64 in enumerate(base64_images):
        content.append({"type": "text", "text": f"Page {i + 1}:"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}})
    content.append({"type": "text", "text": "Check these pages and find if there is a signature, date, name, and surname of a corresponding author."})

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """You are responsible for detecting whether a corresponding author's signature block exists in the given pages.
                Look for: a handwritten or digital signature, a date, and the author's name/surname.
                Return ONLY a JSON object with no extra text, no markdown, no explanation.
                Format:
                {
                    "signature_exists": bool,
                    "date_exists": bool,
                    "date_value": str,
                    "name_exists": bool,
                    "name_value": str,
                    "surname_exists": bool,
                    "surname_value": str
                }
                Use empty string "" if a field is not found."""
            },
            {"role": "user", "content": content}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)


# ── main checker ─────────────────────────────────────────────────────────────

def check_3a_form(main_name: str, md_dir: str = "output_of_forms", pdf_dir: str = "data") -> dict:
    md_file_path  = f"{md_dir}/{main_name}.md"
    pdf_file_path = f"{pdf_dir}/{main_name}.pdf"

    with open(md_file_path, "r") as f:
        md_text = f.read()

    corresponding_author = find_corresponding_author(md_text)
    title_1              = find_title_in_1(md_text)          # NEW
    title_2              = find_title_in_section(md_text)
    signature            = check_signature_in_pages(pdf_file_path)

    return {
        "form_name": main_name,
        **corresponding_author,
        **title_1,                                            # NEW
        **title_2,
        **signature,
    }


# ── main loop ─────────────────────────────────────────────────────────────────
if __name__ == "__main__": 
    
    data_path = "data"
    form_dict = get_the_list_of_types(data_path)
    _3a_ = form_dict["3a"]

    all_results = {}

    for form in _3a_:
        file_path = Path(form)
        main_name, _ = os.path.splitext(file_path.name)

        print(f"Processing: {main_name}")
        result = check_3a_form(main_name)
        all_results[main_name] = result

    print("\n===== FULL RESULTS =====")
    print(json.dumps(all_results, indent=2))