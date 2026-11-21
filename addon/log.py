def log(*args):
    """To stdout: Anki shows anything written to stderr as an error window."""
    print("[practice deck]", *args, flush=True)
