import re
from .mgf import MGFParser

class MGFParserPLGS(MGFParser):
    scan_regexp = re.compile(r'lepeakid:(\d+):', re.IGNORECASE)