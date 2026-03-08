import re
import json
import logging
from utils.which_type import get_the_list_of_types
from pathlib import Path
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs.txt", encoding="utf-8"),
        logging.StreamHandler()  # aynı anda terminale de yazar
    ]
)
log = logging.getLogger(__name__)

load_dotenv()
client = OpenAI()



#########################
# --- TITLE GRAMMAR --- #
#########################

def get_the_main_title(md_text: str) -> str:
    headings = re.findall(r'^(#{1,6})\s+(.*)', md_text, re.MULTILINE)
    if not headings:
        return ""
    headings.sort(key=lambda x: len(x[0]))
    return headings[0][1]


def check_title_grammar_llm(title: str) -> dict:
    if not title:
        return {"title_name": "", "title_grammar": False}

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """You are responsible for checking the grammar of a given title.
                Return ONLY a JSON object with no extra text, no markdown, no explanation.
                Format: {"title_name": str, "title_grammar": bool}
                - "title_name" is the original title as given
                - "title_grammar" is true if the title is grammatically correct, false otherwise"""
            },
            {"role": "user", "content": title}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)


##########################
# --- ABSTRACT CHECK --- #
##########################

def get_abstract_text(md_text: str) -> str:
    # Matches: ## Abstract: (with or without **)
    pattern = r'^#{1,6}\s+\*?Abstract:?\*?\s*\n(.*?)(?=\nKeywords:|\n\*\*Keywords|\n#{1,6}\s|\Z)'
    match = re.search(pattern, md_text, re.DOTALL | re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def check_abstract_llm(abstract_text: str) -> dict:

    if not abstract_text:
        return {"abstract_suitable": False, "abstract_word_count": 0}

    # Count words locally — no need to rely on LLM for counting
    word_count = len(abstract_text.split())

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """You are responsible for checking if an abstract is suitable.
                The abstract must contain a maximum of 250 words to be suitable.
                You will be given the abstract text and its exact word count.
                Return ONLY a JSON object with no extra text, no markdown, no explanation.
                Format: {"abstract_suitable": bool, "abstract_word_count": int}
                - "abstract_suitable" is true if the word count is 250 or fewer, false otherwise
                - "abstract_word_count" is the exact word count provided to you, do not recount"""
            },
            {
                "role": "user",
                "content": f"Abstract text:\n{abstract_text}\n\nExact word count: {word_count}"
            }
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)


##########################
# --- KEYWORDS CHECK --- #
##########################

def get_keywords_text(md_text: str) -> str:
    # Matches: Keywords: or **Keywords:** on same line or next line
    pattern = r'\*{0,2}Keywords:?\*{0,2}\s*(.*?)(?=\n#{1,6}\s|\n\*\*|\Z)'
    match = re.search(pattern, md_text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def check_keywords_llm(keywords_text: str) -> dict:
    if not keywords_text:
        return {"keywords_suitable": False, "keywords_count": 0}

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """You are responsible for checking if the keywords section is suitable.
                The keywords must contain at least 5 keywords to be suitable.
                Count the individual keywords carefully (they may be separated by commas, semicolons, or newlines).
                Return ONLY a JSON object with no extra text, no markdown, no explanation.
                Format: {"keywords_suitable": bool, "keywords_count": int}
                - "keywords_suitable" is true if there are 5 or more keywords, false otherwise
                - "keywords_count" is the exact number of keywords found"""
            },
            {"role": "user", "content": keywords_text}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)


##############################
# --- TITLE NUMBER CHECK --- #
##############################

def get_all_headings(md_text: str) -> list[str]:
    """Extract all numbered headings — supports:
       ## 1. Title
       ## 1.\tTitle
       # **1. Title**
    """
    # Matches with or without **, with tab or space after number
    pattern = r'^#{1,6}\s+\*{0,2}(\d+(?:\.\d+)*\.?)[\s\t]+.*?\*{0,2}\s*$'

    all_headings = []
    for line in md_text.split('\n'):
        match = re.match(pattern, line.strip())
        if match:
            all_headings.append(match.group(1).rstrip('.'))

    return all_headings


def check_numbering(headings: list[str]) -> dict:
    errors = []
    counters = {}

    for heading in headings:
        parts = [int(p) for p in heading.split('.')]
        level = len(parts)
        expected_counter = counters.get(level, 0) + 1

        # Reset deeper levels
        for k in [k for k in counters if k > level]:
            del counters[k]

        if parts[-1] != expected_counter:
            expected_full = '.'.join(str(p) for p in parts[:-1] + [expected_counter])
            errors.append({
                "found": heading,
                "expected": expected_full
            })

        counters[level] = parts[-1]

    return {
        "numbering_correct": len(errors) == 0,
        "errors": errors
    }


def check_heading_numbering(md_text: str) -> dict:
    headings = get_all_headings(md_text)

    if not headings:
        return {"header_numbering_correct": False, "headings_found": [], "errors": ["No numbered headings found"]}

    result = check_numbering(headings)

    return {
        "numbering_correct": result["numbering_correct"],
        "headings_found": headings,
        "errors": result["errors"]
    }



###################################
# --- HARVARD REFERENCE CHECK --- #
###################################

def get_references_text(md_text: str) -> str:
    """Extract references section from md text."""
    # Matches: ## References, ## **References**, ### References etc.
    pattern = r'^#{1,6}\s+\*{0,2}References\*{0,2}\s*\n(.*?)(?=\n#{1,6}\s|\Z)'
    match = re.search(pattern, md_text, re.DOTALL | re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def parse_references(references_text: str) -> list[str]:
    """Split references into individual entries."""
    refs = []
    for line in references_text.split('\n'):
        line = line.strip()
        if line:
            refs.append(line)
    return refs


def check_reference_format_llm(reference: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """You are responsible for checking if a given reference is in Harvard format.
                Harvard format key rules:
                - Author(s): Surname, Initial. (e.g. Jia, X.)
                - Year comes right after authors followed by a dot
                - Article/book title in plain text
                - Journal name should be present (for journal articles)
                - Volume and page number at the end (e.g. 225, p.116126)
                Return ONLY a JSON object with no extra text, no markdown, no explanation.
                Format: {"reference": str, "is_harvard": bool, "reason": str}
                - "reference" is the original reference as given
                - "is_harvard" is true if it follows Harvard format, false otherwise
                - "reason" is a brief explanation of why it is or isn't Harvard format"""
            },
            {"role": "user", "content": reference}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)


def check_references_harvard(md_text: str) -> dict:
    references_text = get_references_text(md_text)

    if not references_text:
        return {"references_found": False, "references": []}

    refs = parse_references(references_text)
    results = [check_reference_format_llm(ref) for ref in refs]

    all_harvard = all(r["is_harvard"] for r in results)

    return {
        "references_found": True,
        "all_harvard": all_harvard,
        "total_references": len(refs),
        "references": results
    }


######################
# --- MAIN CHECK --- #
######################

def check_form(form_path: str, md_dir: str = "output_of_forms") -> dict:
    file_path = Path(form_path)
    root, _ = os.path.splitext(file_path.name)
    md_file_path = f"{md_dir}/{root}.md"

    log.info(f"Starting check: {file_path.name}")

    with open(md_file_path, "r") as f:
        md_text = f.read()

    log.info(f"[{root}] Checking title grammar...")
    title_result = check_title_grammar_llm(get_the_main_title(md_text))
    log.info(f"[{root}] Title: {title_result}")

    log.info(f"[{root}] Checking abstract...")
    abstract_result = check_abstract_llm(get_abstract_text(md_text))
    log.info(f"[{root}] Abstract: {abstract_result}")

    log.info(f"[{root}] Checking keywords...")
    keywords_result = check_keywords_llm(get_keywords_text(md_text))
    log.info(f"[{root}] Keywords: {keywords_result}")

    log.info(f"[{root}] Checking heading numbering...")
    numbering_result = check_heading_numbering(md_text)
    log.info(f"[{root}] Numbering: {numbering_result}")

    log.info(f"[{root}] Checking references...")
    references_result = check_references_harvard(md_text)
    log.info(f"[{root}] References: {references_result}")

    log.info(f"[{root}] ✔ Done")

    return {
        "form_name": root,
        **title_result,
        **abstract_result,
        **keywords_result,
        **numbering_result,
        "references": references_result,
    }

if __name__ == "__main__": 
    data_path = "data"
    form_dict = get_the_list_of_types(data_path)
    form = form_dict["unknown"]
    # --- MAIN LOOP ---
    all_results = {}

    for form_path in form:
        result = check_form(form_path)
        all_results[Path(form_path).stem] = result
        print(json.dumps(result, indent=2))

    print("\n===== FULL RESULTS =====")
    print(json.dumps(all_results, indent=2))