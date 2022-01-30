from pprint import pprint


class Printer:
    level = 1
    separator = None
    separator_length = 50

    def inkjet(*args: any,
               level: int = 1,
               is_pprint: bool = False,
               separator: str = None):
        if separator is None:
            separator = Printer.separator
        if level <= Printer.level:
            if separator is not None:
                print(separator * Printer.separator_length)
            if is_pprint:
                pprint(*args)
            else:
                print(*args)
