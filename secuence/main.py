from bs4 import BeautifulSoup
from odf.opendocument import load

import regex_spm
import re
from sys import argv
import subprocess


def usage():
    print(f"""\
USAGE:
{argv[0]} <filename> <output>
""")
    exit(0)


if len(argv) < 3:
    usage()

filename = argv[1]
tofile = argv[2]

doc = load(filename)
content = doc.xml().decode('utf-8')
bs = BeautifulSoup(content, features="xml")
table = bs.find("table")


rows = [row for row in table.find_all("table:table-row")]

steps_start = 0
scheme = ""
authors = {}
branches = []

for r, row in enumerate(rows):
    cells = row.find_all("table:table-cell")
    cell = cells[0]
    # get id_name
    if(cell.get_text() == "ID"):
        pattern = re.compile("\d+.\d+")
        id = pattern.findall(cells[1].get_text())[0]
        name = rows[r+1].find_all("table:table-cell")[1].get_text()
        scheme = str(id) + " " + name

    # get steps with authors
    if(cell.get_text() == "PASO"):
        steps_start = r+1
        for i, author in enumerate(rows[r].find_all("table:table-cell")):
            if(i > 0):
                authors[(author.get_text())] = {}
        continue

    # get steps
    if(steps_start != 0):
        if(cell.get_text() == "Flujos Alternos"):
            authors["limit"] = r-steps_start
            steps_start = 0

            # get_branches
            branches = [branch.get_text()
                        for branch in rows[r+1].find_all("text:list-item")]

            continue
        for step, key in enumerate(authors.keys()):
            text = cells[step+1].get_text()
            if(text != ""):
                authors[key] |= {(r-steps_start+1, text)}


count = {
    "Clic": 0,
    "Despliega": 0
}


def time_block(block, forever=False):
    msg = f"activate {block}\n"
    if(not forever):
        msg += f"deactivate {block}\n"
    return msg


actor = "_a"
main = "_m"
interface = "_b"
structure = "_s"
database = "_d"


def sequence_diagram(scheme, authors: dict, branches: list):
    with open(f"{tofile}", "w") as f:
        f.write("@startuml\n")
        f.write(f'mainframe {scheme}\n')

        for author in authors.keys():
            if(author != "SISTEMA" and author != "limit"
               or len(authors) == 2):
                f.write(f"actor {author} as {actor}\n")
                f.write(f"boundary Principal as {main}\n")
                f.write(f"boundary {author} as {interface}\n")
                f.write(f"control {author} as {structure}\n")
                f.write(f"entity {author} as {database}\n")
        output = ""
        #limit = author["limit"]
        for i in range(1, authors["limit"]+1):
            for author in authors.keys():
                if(author == "limit"):
                    continue
                if(i in authors[author].keys()):
                    output = match(authors[author][i], step=i)
                    output = branch(step=i, output=output)
                    f.write(output)
        f.write("@enduml")


def match(msg, step=0):
    ret = ""
    match regex_spm.search_in(msg):
        case r"clic" | r"clic" as token:
            match count["Clic"]:
                case 0:
                    ret += f"{actor}->{main} : {token.string}\n"
                    ret += time_block(main, forever=True)
                case others:
                    ret += f"{actor}->{interface} : {token.string}\n"
                    ret += time_block(interface)
            count["Clic"] += 1

        case r"Digita" | r"digita" | r"Selecciona" as token:
            ret += f"{actor}->{interface} : Digita los campos\n"
            ret += time_block(interface)

        case r"Invoca" | r"invoca" as token:
            pattern = re.compile(r"(\d+.\d+)[ ]+(\w+)[ ]+(\w+)")
            found = pattern.findall(token.string)[0]
            ref = ' '.join(found)
            ret += f"{interface}->>{structure}: {found[1] + found[2] + f'({found[2]})'}\n"
            ret += time_block(structure)

            ret += "group ref\n"
            ret += f"{structure}->>{database}: {ref}\n"
            ret += time_block(database)
            ret += "end\n"

            ret += f"{structure}-->>{interface}: {found[1] + found[2] + f'({found[2]})'}\n"

        case r"Muestra" | r"muestra" | r"retorna" as token:
            ret += f"{structure} -->> {interface} : {token.string}\n"
            ret += time_block(interface)

        case r"Alerta" | r"alerta" | r"registrado" as token:

            ret += f"{interface} -->>{structure}: {token.string}'\n"
            ret += time_block(structure)

        case r"Despliega" as token:
            ret += f"{main}->{interface}: {token.string}\n"
            ret += time_block(interface)

        case other:
            pass

    return ret

# branches


def branch(step=0, output=""):
    ret = ""
    pattern = re.compile(
        "En el paso (\d+) del flujo normal de eventos si (\D+) entonces (\D+) y vuelve al paso (\d+)")
    for branch in branches:
        found = pattern.findall(branch)
        if found == []:
            return output
        alt_start = int(found[0][0])
        alt_end = int(found[0][3])
        if(step == alt_start):
            ret += "alt\n"
            ret += output
            ret += "else\n"
            ret += match(found[0][1])
            ret += match(found[0][2])
            ret += "end\n"
            branches.remove(branch)
            return ret
    return output


sequence_diagram(scheme, authors, branches)

subprocess.run(["plantuml", tofile])
