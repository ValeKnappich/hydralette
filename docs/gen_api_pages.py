from pathlib import Path

import mkdocs_gen_files

import hydralette

nav = mkdocs_gen_files.Nav()  # type: ignore


def get_all_members():
    return ["hydralette." + member_name for member_name in hydralette.__all__]


print(get_all_members())

for member in get_all_members():
    parts = member.split(".")
    doc_path = Path("/".join(parts[1:]) + ".md")
    full_doc_path = Path("reference", doc_path)

    if parts[-1] == "__init__":
        parts = parts[:-1]
    elif parts[-1] == "__main__":
        continue
    nav[parts[1:]] = doc_path.as_posix()

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        fd.write(f"::: {member}")

with mkdocs_gen_files.open("reference/API.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
