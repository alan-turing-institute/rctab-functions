"""Force our Azure function to run, regardless of the time."""

import types

from usage import main

if __name__ == "__main__":
    main(types.SimpleNamespace(past_due=True))
