import os


def get_the_list_of_types(data_path: str) -> list:
    form_list = os.listdir(data_path)
    _3a = []
    _3b = []
    _3c = []
    _3d = []
    unknown = [] # Let the user pick what type of this form

    for form in form_list: 
        full_path_form = os.path.join(data_path, form)
        if "3a" in full_path_form: 
            _3a.append(full_path_form)
        elif "3b" in full_path_form: 
            _3b.append(full_path_form)
        elif "3c" in full_path_form: 
            _3c.append(full_path_form)
        elif "3d" in full_path_form: 
            _3d.append(full_path_form)
        else:
            unknown.append(full_path_form)

    list_dict = {
        "3a": _3a,
        "3b": _3b,
        "3c": _3c,
        "3d": _3d,
        "unknown": unknown
    }
    return list_dict
if __name__ == "__main__": 
    data_path = "data"
    forms = get_the_list_of_types(data_path)
    print(forms)