"""Allow `python -m mdmaker`."""
from .cli import main
import sys
sys.exit(main())
