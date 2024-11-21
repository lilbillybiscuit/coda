

color_mapping = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
    "white": "\033[97m",
    "black": "\033[30m",
    "gray": "\033[90m",
    "grey": "\033[90m",
    "reset": "\033[0m"
}

class Color:
    @staticmethod
    def colorize(color: str, text: str, bold: bool = False, italic: bool = False, **kwargs):
        """Return colored text string with optional bold and italic formatting"""
        formatting = ""
        if bold:
            formatting += "\033[1m"
        if italic:
            formatting += "\033[3m"

        if 'flush' not in kwargs:
            kwargs['flush'] = True
        return print(f"{formatting}{color_mapping[color]}{text}{color_mapping['reset']}", **kwargs)

    # same method as above, but for input. use the above method for output
    @staticmethod
    def colorize_input(color: str, text:str, bold: bool = False, italic: bool = False, **kwargs)->str:
        """Return colored text string with optional bold and italic formatting"""
        if 'end' not in kwargs:
            kwargs['end'] = ' '
        Color.colorize(color, text, bold, italic, **kwargs)
        return input()


    @staticmethod
    def color_text(color: str, text: str, **kwargs):
        return print(f"{color_mapping[color]}{text}{color_mapping['reset']}", **kwargs)

    @staticmethod
    def bold_color_text(color: str, text: str, **kwargs):
        return print(f"\033[1{color_mapping[color]}{text}{color_mapping['reset']}", **kwargs)

    @staticmethod
    def italics_color_text(color: str, text: str, **kwargs):
        return print(f"\033[3{color_mapping[color]}{text}{color_mapping['reset']}", **kwargs)

    @staticmethod
    def start_color(color: str):
        return print(color_mapping[color], end='', flush=True)

    @staticmethod
    def end_color():
        return print(color_mapping["reset"], end='', flush=True)