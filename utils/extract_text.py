import pymupdf4llm
import pathlib
import os 
from pathlib import Path
from utils.which_type import get_the_list_of_types

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.output import text_from_rendered
from pathlib import Path
import os
from markitdown import MarkItDown


def extract_text(form_path_list: str):

    for form_path in form_path_list:
        file_path = Path(form_path)
        sub_name_file = file_path.name
        root, extension = os.path.splitext(sub_name_file)

        # Convert the document to a markdown string
        md_text = pymupdf4llm.to_markdown(form_path)

        # Write the text to an output file in UTF-8 encoding
        output_path = pathlib.Path(f"output_of_forms/{root}.md")
        output_path.write_bytes(md_text.encode("utf-8"))

        print(f"Markdown content saved to {output_path}")


def extract_text_for_paper(form_path_list: list):
    # Load models once, reuse for all files
    models = create_model_dict()

    for form_path in form_path_list:
        file_path = Path(form_path)
        root, extension = os.path.splitext(file_path.name)

        md = MarkItDown(enable_plugins=False) # Set to True to enable plugins
        result = md.convert(form_path)
        markdown_text = result.text_content

        output_path = Path(f"output_of_forms/{root}.md")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        print(f"Converted: {file_path.name} → {output_path}")




if __name__ == "__main__": 
    data_path = "data"
    forms = get_the_list_of_types(data_path)
    _3a = forms["3a"]
    _3b = forms["3b"]
    _3c = forms["3c"]
    _3d = forms["3d"]
    
    # extract_text(_3a)
    # extract_text(_3b)
    # extract_text(_3c)
    # extract_text(_3d)

    unknown = forms["unknown"]

    extract_text_for_paper(unknown)