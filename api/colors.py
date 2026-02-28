##### PRINT TO CONSOLE CONFIG #####
class tty_colors:
    # Text Colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Bright Text Colors
    BRIGHT_BLACK = '\033[90m'    # Dark Gray
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

    # Background Colors
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'

    # Bright Background Colors
    BG_BRIGHT_BLACK = '\033[100m'
    BG_BRIGHT_RED = '\033[101m'
    BG_BRIGHT_GREEN = '\033[102m'
    BG_BRIGHT_YELLOW = '\033[103m'
    BG_BRIGHT_BLUE = '\033[104m'
    BG_BRIGHT_MAGENTA = '\033[105m'
    BG_BRIGHT_CYAN = '\033[106m'
    BG_BRIGHT_WHITE = '\033[107m'

    # Text Styles
    RESET = '\033[0m'       # Reset all formatting
    BOLD = '\033[1m'        # Bold text
    DIM = '\033[2m'         # Dim text
    ITALIC = '\033[3m'      # Italic text
    UNDERLINE = '\033[4m'   # Underlined text
    BLINK = '\033[5m'       # Blinking text
    REVERSE = '\033[7m'     # Reverse colors (swap fg/bg)
    STRIKETHROUGH = '\033[9m'  # Strikethrough text

    # Semantic color names for different log levels
    HEADER_1 = BOLD + YELLOW
    HEADER_2 = BOLD + BRIGHT_CYAN
    HEADER_3 = BOLD + BRIGHT_MAGENTA
    INFO = BRIGHT_BLUE
    SUCCESS = BRIGHT_GREEN
    ERROR = BOLD + BG_RED
    DEBUG = BRIGHT_BLACK
    CRITICAL = BOLD + BRIGHT_RED